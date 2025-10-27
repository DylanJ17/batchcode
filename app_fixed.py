import streamlit as st
import sys, os

st.title("Batch Code Validator")
st.write("🔄 Running batch validation... please wait...")

try:
    # @title
    from datetime import datetime, timedelta
    import calendar
    import ipywidgets as widgets
    from IPython.display import display, clear_output, FileLink, HTML
    import pandas as pd
    import os
    import re
    from typing import List, Tuple, Optional, Dict, Any
    import warnings
    import logging
    
    # Attempt to import Colab-specific module
    try:
        from google.colab import files
        IS_COLAB_ENV = True
    except ImportError:
        IS_COLAB_ENV = False
    
    warnings.filterwarnings('ignore')
    
    # --- Logging Setup ---
    logger = logging.getLogger(__name__)
    if not logger.handlers: # Ensure handlers are not added multiple times in Jupyter
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    class BatchCodeValidator:
        """Enhanced batch code validator trained on historical Philip Kingsley data."""
    
        def __init__(self):
            self.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Status', 'Confidence'])
            self.historical_patterns = self._load_historical_patterns()
            self.current_year = datetime.now().year
    
        def _load_historical_patterns(self) -> Dict[str, Dict[str, Any]]:
            """
            Load and analyze historical batch code patterns.
            This has been updated with new findings from user-provided data.
            """
            return {
                # NEW PATTERN (Identified from user data)
                'yddd_bb': {
                    'pattern': r'^(\d)(\d{3})(\d{2})$',
                    'description': 'Year(Y) + Julian Day(DDD) + Batch(BB)',
                    'examples': ['500903', '505201', '510402']
                },
                'ddmmyyyy_variants': {
                    'pattern': r'^(\d{1,2})(\d{1,2})(\d{2})(\d{1,3})$',
                    'description': 'Day/Month/Year with suffix',
                    'examples': ['27124128', '22924124', '25624125']
                },
                'ddmmyy_variants': {
                    'pattern': r'^(\d{2})(\d{2})(\d{2})$',
                    'description': 'Day/Month/Year or Month/Day/Year',
                    'examples': ['052024', '202401', '212306']
                },
                'julian_with_suffix': {
                    'pattern': r'^(\d{3})(\d{2})(\d{1,3})$',
                    'description': 'Julian day + Year + 1 to 3 digit suffix',
                    'examples': ['1872417', '2402416', '250241']
                },
                'mixed_alpha': {
                    'pattern': r'^(\d{3,5})(\d{2})([A-Z]+)$',
                    'description': 'Date digits + alphabetic suffix',
                    'examples': ['17924AW', '20424P', '10224O']
                },
                'prefix_yymm_suffix': {
                    'pattern': r'^([A-Z])(\d{2})(\d{2})([A-Z0-9]+)$',
                    'description': 'Prefix + Year(YY) + Month(MM) + Suffix',
                    'examples': ['H2401B']
                },
                'special_prefix': {
                    'pattern': r'^([A-Z])(\d{2,4})([A-Z0-9]+)$',
                    'description': 'Letter prefix + ambiguous date + suffix (lower confidence fallback)',
                    'examples': ['H1619A']
                },
            }
    
        @staticmethod
        def is_leap_year(year: int) -> bool:
            """Check if a year is a leap year."""
            return calendar.isleap(year)
    
        @staticmethod
        def julian_to_date(year: int, day_of_year: int) -> datetime:
            """Convert Julian day and year to datetime."""
            if not (1 <= day_of_year <= (366 if BatchCodeValidator.is_leap_year(year) else 365)):
                raise ValueError(f"Day of year {day_of_year} is invalid for year {year}.")
            return datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
    
        @staticmethod
        def add_years(date: datetime, years: int = 3) -> datetime:
            """Add years to a date, handling leap year edge cases for Feb 29th."""
            try:
                return date.replace(year=date.year + years)
            except ValueError: # Handles date(2020, 2, 29).replace(year=2021)
                if date.month == 2 and date.day == 29:
                    return date.replace(month=2, day=28, year=date.year + years)
                raise # Re-raise other ValueErrors
    
        def is_valid_expiry(self, expiry_date: datetime) -> bool:
            """Check if expiry date is within a valid range (2015 up to 3 years from today)."""
            today = datetime.now().date()
            max_expiry_dt = datetime(today.year + 3, today.month, today.day)
            min_expiry_dt = datetime(2015, 1, 1)
            return min_expiry_dt.date() <= expiry_date.date() <= max_expiry_dt.date()
    
        @staticmethod
        def _resolve_two_digit_year(yy: int) -> int:
            """ Resolves a two-digit year to a four-digit year. Heuristic: YY < 50 implies 20YY, otherwise 19YY. """
            if not (0 <= yy <= 99):
                raise ValueError("Two-digit year 'yy' must be between 0 and 99.")
            current_century_start = (datetime.now().year // 100) * 100
            if yy < 50:
                return current_century_start + yy
            else:
                return (current_century_start - 100) + yy
    
        def parse_date_variants(self, part1: int, part2: int, yy: int) -> List[datetime]:
            """ Try different date interpretations (DD/MM/YY, MM/DD/YY, MM/YY) and return valid ones. """
            candidates = []
            current_dt = datetime.now()
            current_year = current_dt.year
            resolved_years_to_try = []
            if 0 <= yy <= 99:
                year_2000s = 2000 + yy
                year_1900s = 1900 + yy
                if yy > (current_year % 100 + 5):
                    resolved_years_to_try.append(year_1900s)
                resolved_years_to_try.append(year_2000s)
                if year_1900s == year_2000s and len(resolved_years_to_try) > 1:
                     resolved_years_to_try = [year_2000s]
            else:
                resolved_years_to_try = [yy]
    
            valid_prod_years = [y for y in resolved_years_to_try if 2015 <= y <= (current_year + 1)]
            if not valid_prod_years and resolved_years_to_try:
                logger.debug(f"Date parsing: yy={yy} led to years {resolved_years_to_try}, all filtered by range 2015-{(current_year + 1)}")
    
            max_prod_date_candidate = current_dt + timedelta(days=90)
    
            for year_val in valid_prod_years:
                try: # DD/MM/YYYY
                    if 1 <= part1 <= 31 and 1 <= part2 <= 12:
                        dt = datetime(year_val, part2, part1)
                        if dt <= max_prod_date_candidate: candidates.append(dt)
                except ValueError: logger.debug(f"Failed DD/MM/YYYY for {part1}/{part2}/{year_val}", exc_info=False)
                try: # MM/DD/YYYY
                    if 1 <= part1 <= 12 and 1 <= part2 <= 31:
                        dt = datetime(year_val, part1, part2)
                        if dt not in candidates and dt <= max_prod_date_candidate: candidates.append(dt)
                except ValueError: logger.debug(f"Failed MM/DD/YYYY for {part1}/{part2}/{year_val}", exc_info=False)
    
            if 1 <= part1 <= 12: # Try MM/YY
                for year_val_my in valid_prod_years:
                    try:
                        last_day = calendar.monthrange(year_val_my, part1)[1]
                        dt = datetime(year_val_my, part1, last_day)
                        if dt not in candidates and dt <= max_prod_date_candidate: candidates.append(dt)
                    except ValueError: logger.debug(f"Failed MM/YY for {part1}/{year_val_my}", exc_info=False)
    
            unique_candidates = []
            seen = set()
            for c in sorted(candidates):
                if c not in seen:
                    unique_candidates.append(c)
                    seen.add(c)
            return unique_candidates
    
        def _process_parsed_dates(self, code_part_for_msg: str, prod_date_candidates: List[datetime], suffix: Optional[str]="", base_confidence: float=0.8, format_desc_prefix:str="") -> List[Dict]:
            results = []
            if not prod_date_candidates:
                logger.debug(f"No valid production date candidates for {code_part_for_msg}")
                return []
            for prod_date in prod_date_candidates:
                expiry_date = self.add_years(prod_date, 3)
                if self.is_valid_expiry(expiry_date):
                    res_dict = {'production_date': prod_date, 'expiry_date': expiry_date, 'confidence': base_confidence, 'format_type': f"{format_desc_prefix}" if format_desc_prefix else "Parsed Date"}
                    if suffix: res_dict['suffix'] = suffix
                    results.append(res_dict)
                else: logger.debug(f"Expiry date {expiry_date.strftime('%Y-%m-%d')} for prod {prod_date.strftime('%Y-%m-%d')} invalid.")
            return results
    
        # NEW VALIDATOR METHOD for YDDD BB format
        def validate_yddd_bb(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern 7: YDDD BB (e.g., 500903). Identified from user data."""
            pattern_info = self.historical_patterns.get('yddd_bb', {})
            match = re.match(pattern_info.get('pattern', '^$'), code)
            if not match: return False, "Not YDDD BB pattern", []
    
            try:
                y_str, ddd_str, bb_str = match.groups()
                y_digit, ddd = int(y_str), int(ddd_str)
    
                # Heuristic to determine the full year from a single digit
                current_year = datetime.now().year
                # Candidate year in the current decade
                year_candidate_1 = (current_year // 10) * 10 + y_digit
                # If this candidate is in the future, the code is likely from the previous decade
                if year_candidate_1 > current_year:
                    year = year_candidate_1 - 10
                else:
                    year = year_candidate_1
    
                if not (2015 <= year <= (current_year + 1)):
                    return False, f"Resolved year {year} is out of valid range (2015-current)", []
    
                prod_date = self.julian_to_date(year, ddd)
                expiry_date = self.add_years(prod_date, 3)
    
                if self.is_valid_expiry(expiry_date):
                    return True, f"YDDD BB (Year: {year}, Julian: {ddd}, Batch: {bb_str})", [{
                        'production_date': prod_date,
                        'expiry_date': expiry_date,
                        'julian_day': ddd,
                        'batch': bb_str,
                        'confidence': 0.98, # Very high confidence due to specific structure from data
                        'format_type': 'YDDD BB'
                    }]
            except (ValueError, OverflowError) as e:
                logger.warning(f"Validation error for YDDD BB pattern with code '{code}': {e}", exc_info=False)
    
            return False, f"Invalid data for YDDD BB pattern in code '{code}'", []
    
        def validate_historical_pattern_1(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern: ddmmyyyy variants (like 27124128, 22924124)"""
            pattern_info = self.historical_patterns['ddmmyyyy_variants']
            match = re.match(pattern_info['pattern'], code)
            if not match: return False, "Not historical pattern 1", []
            try:
                day_str, month_str, yy_str, suffix_str = match.groups()
                day, month, yy = int(day_str), int(month_str), int(yy_str)
                candidates = self.parse_date_variants(day, month, yy)
                results = self._process_parsed_dates(f"{day_str}-{month_str}-{yy_str}", candidates, suffix_str, 0.9, "DD/MM/YY or MM/DD/YY")
                if results:
                    for r in results:
                        if r['production_date'].day == day and r['production_date'].month == month: r['format_type'] = "DD/MM/YY + suffix"
                        elif r['production_date'].month == day and r['production_date'].day == month: r['format_type'] = "MM/DD/YY + suffix"
                        else: r['format_type'] = "Parsed Date (MM/YY?) + suffix"
                    return True, f"Historical Pattern 1 ({pattern_info['description']}) Suffix: {suffix_str}", results
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error HistP1 code '{code}': {e}", exc_info=False)
            return False, f"Invalid data historical pattern 1 code '{code}'", []
    
        def validate_historical_pattern_2(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern: ddmmyy or mmddyy (like 052024, 202401)"""
            pattern_info = self.historical_patterns['ddmmyy_variants']
            match = re.match(pattern_info['pattern'], code)
            if not match:
                 if len(code) != 6 or not code.isdigit(): return False, "Not historical pattern 2 (len/type)", []
                 return False, "Not historical pattern 2 (regex mismatch)", []
            try:
                p1_str, p2_str, yy_str = match.groups()
                part1, part2, yy = int(p1_str), int(p2_str), int(yy_str)
                candidates = self.parse_date_variants(part1, part2, yy)
                results = self._process_parsed_dates(f"{p1_str}-{p2_str}-{yy_str}", candidates, base_confidence=0.85, format_desc_prefix="DD/MM/YY or MM/DD/YY")
                if results:
                    for r in results:
                        if r['production_date'].day == part1 and r['production_date'].month == part2: r['format_type'] = "DD/MM/YY"
                        elif r['production_date'].month == part1 and r['production_date'].day == part2: r['format_type'] = "MM/DD/YY"
                        else: r['format_type'] = "MM/YY (End of Month)"
                    return True, f"Historical Pattern 2 ({pattern_info['description']})", results
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error HistP2 code '{code}': {e}", exc_info=False)
            return False, f"Invalid data historical pattern 2 code '{code}'", []
    
        def validate_historical_pattern_3(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern: Julian day + year + suffix (like 1872417, 2402416)"""
            pattern_info = self.historical_patterns['julian_with_suffix']
            match = re.match(pattern_info['pattern'], code)
            if not match: return False, "Not historical pattern 3", []
            try:
                ddd_str, yy_str, suffix_str = match.groups()
                ddd, yy = int(ddd_str), int(yy_str)
                year = self._resolve_two_digit_year(yy)
                if not (2015 <= year <= (self.current_year + 1)): return False, f"Year {year} out of range hist.P3", []
                prod_date = self.julian_to_date(year, ddd)
                expiry_date = self.add_years(prod_date, 3)
                if self.is_valid_expiry(expiry_date):
                    return True, f"Historical Pattern 3 (Julian {ddd}/{year} + suffix: {suffix_str})", [{'production_date': prod_date, 'expiry_date': expiry_date, 'julian_day': ddd, 'suffix': suffix_str, 'confidence': 0.95, 'format_type': 'Julian DDDYY + Suffix'}]
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error HistP3 code '{code}': {e}", exc_info=False)
            return False, f"Invalid data historical pattern 3 code '{code}'", []
    
        def validate_historical_pattern_4(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern: Date digits + alphabetic suffix (like 17924AW, 20424P)"""
            pattern_info = self.historical_patterns['mixed_alpha']
            match = re.match(pattern_info['pattern'], code)
            if not match: return False, "Not historical pattern 4", []
            final_results = []
            try:
                date_part_str, yy_str, alpha_suffix = match.groups()
                yy = int(yy_str)
                if len(date_part_str) == 3:
                    ddd = int(date_part_str)
                    year_resolved = self._resolve_two_digit_year(yy)
                    if 2015 <= year_resolved <= (self.current_year + 1):
                        try:
                            prod_date = self.julian_to_date(year_resolved, ddd)
                            expiry_date = self.add_years(prod_date, 3)
                            if self.is_valid_expiry(expiry_date): final_results.append({'production_date': prod_date, 'expiry_date': expiry_date, 'julian_day': ddd, 'alpha_suffix': alpha_suffix, 'confidence': 0.9, 'format_type': 'Julian DDDYY + Alpha Suffix'})
                        except ValueError: logger.debug(f"HistP4: Invalid Julian {ddd}/{year_resolved} in {code}")
                elif len(date_part_str) == 4:
                    p1 = int(date_part_str[:2]); p2 = int(date_part_str[2:4])
                    candidates = self.parse_date_variants(p1, p2, yy)
                    processed = self._process_parsed_dates(f"{date_part_str}-{yy_str}", candidates, alpha_suffix, 0.85, "DDMMYY/MMDDYY + Alpha")
                    for r_item in processed:
                        r_item['alpha_suffix'] = alpha_suffix
                        if r_item['production_date'].day == p1 and r_item['production_date'].month == p2: r_item['format_type'] = "DDMMYY + Alpha Suffix"
                        elif r_item['production_date'].month == p1 and r_item['production_date'].day == p2: r_item['format_type'] = "MMDDYY + Alpha Suffix"
                        else: r_item['format_type'] = "MMYY (End of Month) + Alpha Suffix"
                    final_results.extend(processed)
                elif len(date_part_str) == 5: logger.warning(f"HistP4: 5-digit date part '{date_part_str}' in '{code}' unhandled.")
                if final_results: return True, f"Historical Pattern 4 ({pattern_info['description']}) Alpha Suffix: {alpha_suffix}", final_results
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error HistP4 code '{code}': {e}", exc_info=False)
            return False, f"Invalid data historical pattern 4 code '{code}'", []
    
        def validate_prefix_yymm_suffix(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern 6: Prefix + YY + MM + Suffix (e.g., H2401B)."""
            pattern_info = self.historical_patterns.get('prefix_yymm_suffix', {})
            match = re.match(pattern_info.get('pattern', '^$'), code)
            if not match: return False, "Not Prefix-YYMM-Suffix pattern", []
            try:
                prefix_str, yy_str, mm_str, suffix_str = match.groups()
                yy, mm = int(yy_str), int(mm_str)
                if not (1 <= mm <= 12): return False, f"Invalid month '{mm_str}' for pattern", []
                year = self._resolve_two_digit_year(yy)
                if not (2015 <= year <= (self.current_year + 1)): return False, f"Year {year} out of range for pattern", []
                last_day_of_month = calendar.monthrange(year, mm)[1]
                prod_date = datetime(year, mm, last_day_of_month)
                expiry_date = self.add_years(prod_date, 3)
                if self.is_valid_expiry(expiry_date):
                    return True, f"Prefix-YYMM-Suffix (Prefix: {prefix_str}, Date: {mm:02d}/{year}, Suffix: {suffix_str})", [{'production_date': prod_date, 'expiry_date': expiry_date, 'prefix': prefix_str, 'suffix': suffix_str, 'confidence': 0.95, 'format_type': 'Prefix-YYMM-Suffix'}]
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error for Prefix-YYMM-Suffix pattern with code '{code}': {e}", exc_info=False)
            return False, f"Invalid data for Prefix-YYMM-Suffix in code '{code}'", []
    
        def validate_special_prefix(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Pattern 5: Special formats like H1619A"""
            pattern_info = self.historical_patterns.get('special_prefix', {})
            match = re.match(pattern_info.get('pattern', '^$'), code)
            if not match: return False, "Not special_prefix pattern", []
            final_results = []
            try:
                prefix_char, date_digits_str, suffix_str = match.groups()
                if len(date_digits_str) == 4:
                    p1 = int(date_digits_str[:2]); p2_or_yy = int(date_digits_str[2:4])
                    year_mmyy = self._resolve_two_digit_year(p2_or_yy)
                    if 1 <= p1 <= 12 and (2015 <= year_mmyy <= self.current_year + 1):
                        try:
                            prod_dt_mmyy = datetime(year_mmyy, p1, calendar.monthrange(year_mmyy, p1)[1])
                            if prod_dt_mmyy <= (datetime.now() + timedelta(days=90)):
                               expiry_dt_mmyy = self.add_years(prod_dt_mmyy, 3)
                               if self.is_valid_expiry(expiry_dt_mmyy): final_results.append({'production_date': prod_dt_mmyy, 'expiry_date': expiry_dt_mmyy, 'prefix': prefix_char, 'suffix': suffix_str, 'confidence': 0.75, 'format_type': f"Special Prefix ({prefix_char}) + MMYY ({p1:02d}/{p2_or_yy:02d}) + Suffix ({suffix_str})"})
                        except ValueError: pass
                    candidates_ddmmyy_etc = self.parse_date_variants(p1, p2_or_yy, p2_or_yy)
                    processed_ddmmyy = self._process_parsed_dates(date_digits_str, candidates_ddmmyy_etc, base_confidence=0.70)
                    for r in processed_ddmmyy:
                        r.update({'prefix': prefix_char, 'suffix': suffix_str})
                        r['format_type'] = f"Special Prefix ({prefix_char}) + Parsed({date_digits_str}) + Suffix ({suffix_str})"
                    final_results.extend(processed_ddmmyy)
                elif len(date_digits_str) == 3: logger.warning(f"special_prefix: 3-digit date part '{date_digits_str}' in '{code}' ambiguous.")
                elif len(date_digits_str) == 2: logger.warning(f"special_prefix: 2-digit date part '{date_digits_str}' in '{code}' unhandled.")
                if final_results:
                    unique_final_results = []
                    seen_dates = set()
                    for res_u in sorted(final_results, key=lambda x_u: x_u['production_date']):
                        if res_u['production_date'] not in seen_dates: unique_final_results.append(res_u); seen_dates.add(res_u['production_date'])
                    if unique_final_results: return True, f"Special Prefix (Prefix: {prefix_char}, Suffix: {suffix_str})", unique_final_results
            except (ValueError, OverflowError) as e: logger.warning(f"Validation error for special_prefix with code '{code}': {e}", exc_info=False)
            return False, f"Invalid data for special_prefix in code '{code}'", []
    
        def validate_legacy_formats(self, code: str) -> Tuple[bool, str, List[dict]]:
            """Legacy validation for backward compatibility (DDDYYBB and YYDDD)."""
            results = []
            current_year_val = self.current_year
            if len(code) == 7 and code.isdigit():
                try:
                    ddd, yy, batch_suffix = int(code[:3]), int(code[3:5]), code[5:7]
                    year = self._resolve_two_digit_year(yy)
                    if 2015 <= year <= (current_year_val + 1):
                        prod_date = self.julian_to_date(year, ddd)
                        expiry_date = self.add_years(prod_date, 3)
                        if self.is_valid_expiry(expiry_date): results.append({'production_date': prod_date, 'expiry_date': expiry_date, 'batch': batch_suffix, 'confidence': 0.8, 'format_type': 'Legacy DDDYYBB (Julian)'})
                except (ValueError, OverflowError) as e: logger.debug(f"Legacy DDDYYBB error '{code}': {e}", exc_info=False)
            if len(code) >= 5 and code[:5].isdigit():
                try:
                    yy, ddd = int(code[:2]), int(code[2:5])
                    suffix_val = code[5:] if len(code) > 5 else ""
                    year = self._resolve_two_digit_year(yy)
                    if 2015 <= year <= (current_year_val + 1):
                        prod_date = self.julian_to_date(year, ddd)
                        expiry_date = self.add_years(prod_date, 3)
                        if self.is_valid_expiry(expiry_date):
                            is_dup = any(r['format_type'] == 'Legacy DDDYYBB (Julian)' and r['production_date'] == prod_date for r in results) if len(code)==7 else False
                            if not is_dup: results.append({'production_date': prod_date, 'expiry_date': expiry_date, 'suffix': suffix_val, 'confidence': 0.8, 'format_type': 'Legacy YYDDD (Julian)' + (' + Suffix' if suffix_val else '')})
                except (ValueError, OverflowError) as e: logger.debug(f"Legacy YYDDD error '{code}': {e}", exc_info=False)
            if results: return True, "Legacy Format Match", results
            return False, "No legacy format match", []
    
        def analyze_batch_code(self, code: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
            """ Comprehensive batch code analysis using historical and legacy patterns. """
            code_orig = code.strip()
            cleaned_code = re.sub(r'[-_./\\s]', '', code_orig.upper())
            if not cleaned_code: return False, "Code empty after cleaning" if code_orig else "Empty code", []
    
            validators = [
                # Add new, more specific patterns first for higher priority
                ('Historical-7 (YDDD-BB)', self.validate_yddd_bb),
                ('Historical-6 (Prefix-YYMM-Suffix)', self.validate_prefix_yymm_suffix),
                ('Historical-3 (Julian DDDYY+Suffix)', self.validate_historical_pattern_3),
                ('Historical-1 (DDMMYY+Suffix like)', self.validate_historical_pattern_1),
                ('Historical-4 (Date+Alpha Suffix)', self.validate_historical_pattern_4),
                ('Historical-2 (DDMMYY or MMDDYY 6-digit)', self.validate_historical_pattern_2),
                ('Legacy Formats (DDDYYBB, YYDDD)', self.validate_legacy_formats),
                ('Historical-5 (Special Prefix Fallback)', self.validate_special_prefix),
            ]
            all_interpretations: List[Dict[str, Any]] = []
            for f_name_prefix, val_func in validators:
                try:
                    valid, msg, interp_list = val_func(cleaned_code)
                    if valid and interp_list:
                        for interp_dict in interp_list:
                            interp_dict['format_name_source'] = f_name_prefix
                            interp_dict['parsing_message'] = msg
                            all_interpretations.append(interp_dict)
                except Exception as e: logger.error(f"Exception {f_name_prefix} code '{cleaned_code}': {e}", exc_info=True)
    
            if all_interpretations:
                
                # --- Disambiguation preference: if both YDDD and DDDYY-style matches exist, prefer DDDYY ---
                has_yddd = any(i.get('format_type') == 'YDDD BB' for i in all_interpretations)
                has_dddyy = any(i.get('format_type') in ('Julian DDDYY + Suffix','Julian DDDYY + Alpha Suffix','Legacy DDDYYBB (Julian)') for i in all_interpretations)
                if has_yddd and has_dddyy:
                    all_interpretations = [i for i in all_interpretations if i.get('format_type') != 'YDDD BB']
                # ---------------------------------------------------------------------------
    
                unique_interpretations_final = []
                seen_keys = set()
                for interp in sorted(all_interpretations, key=lambda x: x.get('confidence', 0.0), reverse=True):
                    key_tuple = (interp['production_date'].toordinal(), interp['expiry_date'].toordinal(), interp.get('format_type', ''), interp.get('suffix', ''), interp.get('batch', ''), interp.get('prefix', ''))
                    if key_tuple not in seen_keys: unique_interpretations_final.append(interp); seen_keys.add(key_tuple)
                if not unique_interpretations_final: return False, "No valid interpretations after filtering", []
                unique_interpretations_final.sort(key=lambda x: x.get('confidence', 0.0), reverse=True)
                num_found = len(unique_interpretations_final)
                return True, f"Found {num_found} valid interpretation{'s' if num_found > 1 else ''}", unique_interpretations_final
            else: return False, "No valid date patterns found by any validator", []
    
    class BatchCodeGUI:
        """Enhanced GUI for batch code validation with historical pattern matching."""
    
        def __init__(self):
            self.validator = BatchCodeValidator()
            self.date_format_preference = 'UK'
            self.setup_styles()
            self.create_widgets()
            self.setup_callbacks()
            self.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Days To Expiry', 'Expiry Status', 'Confidence', 'Details'])
    
        def setup_styles(self):
            """Define custom styles for widgets, including new expiry status styles."""
            self.main_style = """
            <style>
            .batch-code-app { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 1200px; margin: 0 auto; }
            .result-success { color: #28a745; font-weight: bold; }
            .result-error { color: #dc3545; font-weight: bold; }
            .result-info { color: #17a2b8; font-weight: bold; }
            .code-info {
                background: #f8f9fa; padding: 10px; border-radius: 5px;
                margin: 10px 0; border: 1px solid #e9ecef; border-left-width: 5px;
            }
            .historical-note { background: #e8f4f8; padding: 8px; border-left: 4px solid #17a2b8; margin: 5px 0; }
            .confidence-high { color: #28a745; }
            .confidence-medium { color: #fd7e14; }
            .confidence-low { color: #dc3545; }
            .status-expired { background-color: #ffebee !important; border-left-color: #c62828 !important; }
            .status-expires-soon-30 { background-color: #fff3e0 !important; border-left-color: #ef6c00 !important; }
            .status-expires-soon-90 { background-color: #fffde7 !important; border-left-color: #fbc02d !important; }
            .status-good { background-color: #e8f5e9 !important; border-left-color: #388e3c !important; }
            .expiry-text-expired { color: #c62828; font-weight: bold; }
            .expiry-text-soon-30 { color: #ef6c00; font-weight: bold; }
            .expiry-text-soon-90 { color: #f9a825; font-weight: bold; }
            .expiry-text-good { color: #388e3c; }
            h3 { border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 15px; }
            .settings-box label { font-weight: bold; margin-right: 10px; }
            .widget-toggle-buttons .widget-label { margin-right: 10px; }
            </style>
            """
    
        def _get_expiry_status_info(self, days_to_expiry: int) -> Tuple[str, str, str]:
            """ Determines the CSS class and descriptive text for expiry status. """
            if days_to_expiry < 0:
                return "status-expired", "expiry-text-expired", f"⚠️ Expired {abs(days_to_expiry)} days ago"
            elif days_to_expiry <= 30:
                return "status-expires-soon-30", "expiry-text-soon-30", f"❗ Expires in {days_to_expiry} days (Critical)"
            elif days_to_expiry <= 90:
                return "status-expires-soon-90", "expiry-text-soon-90", f" Expires in {days_to_expiry} days (Soon)"
            else:
                return "status-good", "expiry-text-good", f"Expires in {days_to_expiry} days (Good)"
    
        def _format_datetime_for_display(self, dt: datetime, include_day_name: bool = True) -> str:
            """ Formats a datetime object based on the current date_format_preference. """
            format_str = '%d/%m/%Y' # UK default
            if self.date_format_preference == 'US':
                format_str = '%m/%d/%Y'
    
            if include_day_name:
                return dt.strftime(f"{format_str} (%A)")
            else:
                return dt.strftime(format_str)
    
        def create_widgets(self):
            """Create all GUI widgets with improved styling."""
            self.title = widgets.HTML(
                value=f'{self.main_style}<div class=\"batch-code-app\"><h1 style=\"color: #0078D7; text-align: center; margin-bottom: 10px;\">📦 Philip Kingsley Batch Code Reader</h1></div>'
            )
            self.code_input = widgets.Text(value='', description='Batch Code:', placeholder='Enter batch code (e.g., 27124128, 17924AW)', layout=widgets.Layout(width='600px', margin='5px'), style={'description_width': '100px'})
            self.multi_code_input = widgets.Textarea(value='', description='Multiple Codes:', placeholder='Enter multiple batch codes, one per line...', layout=widgets.Layout(width='600px', height='120px', margin='5px'), style={'description_width': '100px'})
            self.multi_submit_button = widgets.Button(description='🔍 Analyze Multiple Codes', layout=widgets.Layout(width='220px', height='40px', margin='5px'), button_style='info', icon='search')
            self.date_format_toggle = widgets.ToggleButtons(options=[('UK (DD/MM/YY)', 'UK'), ('US (MM/DD/YY)', 'US')], value='UK', description='Date Display:', button_style='', tooltips=['Display dates as Day/Month/Year', 'Display dates as Month/Day/Year'], style={'description_width': 'auto', 'button_width': '120px'})
            self.export_button = widgets.Button(description='📊 Export to CSV', layout=widgets.Layout(width='150px', height='40px', margin='5px'), button_style='success', icon='file-excel-o')
            self.clear_button = widgets.Button(description='🗑️ Clear All', layout=widgets.Layout(width='120px', height='40px', margin='5px'), button_style='warning', icon='trash')
            self.test_historical_button = widgets.Button(description='🧪 Test Historical Patterns', layout=widgets.Layout(width='200px', height='40px', margin='5px'), button_style='primary', icon='flask')
            self.output = widgets.Output()
            self.progress = widgets.IntProgress(value=0, min=0, max=100, description='Progress:', bar_style='info', style={'bar_color': '#0078D7'}, layout=widgets.Layout(width='500px', visibility='hidden'))
            self.create_tabs()
    
        def create_tabs(self):
            """Create tabbed interface."""
            single_tab_content = [widgets.HTML('<h3>🔍 Single Code Analysis</h3>'), self.code_input, widgets.HTML('<p><i>Results will appear below as you type. Uses historical pattern matching.</i></p>')]
            multi_tab_content = [widgets.HTML('<h3>📊 Batch Processing</h3>'), self.multi_code_input, widgets.HBox([self.multi_submit_button, self.progress]), widgets.HTML('<p><i>Process multiple codes at once. Results can be exported.</i></p>')]
            settings_export_tab_content = [widgets.HTML('<h3>⚙️ Settings, Export & Utilities</h3>'), widgets.HTML("<div class='settings-box'></div>"), self.date_format_toggle, widgets.HTML("<hr style='margin: 15px 0;'/>"), widgets.HBox([self.export_button, self.clear_button, self.test_historical_button]), widgets.HTML('<p><i>Configure date display, export batch results, clear all data, or test historical pattern recognition.</i></p>')]
            help_tab_content = [self.create_help_content()]
            self.tabs = widgets.Tab(children=[widgets.VBox(single_tab_content), widgets.VBox(multi_tab_content), widgets.VBox(settings_export_tab_content)])
            self.tabs.set_title(0, '🔍 Single Code'); self.tabs.set_title(1, '📊 Batch Process'); self.tabs.set_title(2, '⚙️ Settings & Export');
            self.main_container = widgets.VBox([self.title, self.tabs, self.output])
    
        def create_help_content(self) -> widgets.HTML:
            help_html_parts = ["<div class=\"batch-code-app\"><h3>📚 Batch Code Analyzer Help</h3>", "<div class=\"historical-note\"><strong>🎯 This analyzer uses known Philip Kingsley batch code patterns.</strong><br/>It attempts to match codes against these patterns to determine production and expiry dates. Confidence scores indicate the reliability of an interpretation.</div>", "<h4>Supported Historical Patterns:</h4>"]
            for name, p_info in self.validator.historical_patterns.items():
                status_info = " <strong class='result-warning'>(Note: This pattern definition requires review)</strong>" if p_info.get('status') == 'needs_review' else ""
                examples_str = ", ".join(p_info.get('examples', []))
                help_html_parts.append(f"<div class='code-info'><strong>{name.replace('_', ' ').title()}:</strong> {p_info['description']}{status_info}<br/><i>Examples: {examples_str if examples_str else 'N/A'}</i></div>")
            help_html_parts.append("""
                <h4>Legacy Formats Also Checked:</h4>
                <div class='code-info'><strong>DDDYYBB:</strong> Julian Day (3), Year (2), Batch (2)<br/><i>Example: 1872401 (187th day of 2024, batch 01)</i></div>
                <div class='code-info'><strong>YYDDD(+suffix):</strong> Year (2), Julian Day (3), optional suffix<br/><i>Example: 24187AA (2024, 187th day, suffix AA)</i></div>
                <h4>🔧 Key Features:</h4>
                <ul><li><strong>Pattern Matching:</strong> Recognizes multiple PK-specific formats.</li><li><strong>Confidence Scoring:</strong> Indicates reliability of interpretations.</li><li><strong>Date Handling:</strong> Parses DD/MM/YY, MM/DD/YY, Julian dates. Smart 2-digit year conversion.</li><li><strong>Date Ranges:</strong> Production: 2015 - (Current Year + 1). Expiry: Production + 3 years (within reasonable overall limits).</li><li><strong>Real-time Validation (Single Code):</strong> Instant feedback.</li><li><strong>Date Format Toggle:</strong> Switch between UK (DD/MM/YY) and US (MM/DD/YY) display.</li></ul>
                <div class=\"historical-note\"><strong>💡 Pro Tip:</strong> If multiple interpretations are found, the one with the highest confidence is usually the most likely. Always double-check if critical.</div>
            </div>""")
            return widgets.HTML("".join(help_html_parts))
    
        def _on_date_format_change(self, change: Dict[str, Any]):
            """Callback for when the date format preference changes."""
            self.date_format_preference = change['new']
            logger.info(f"Date display format changed to: {self.date_format_preference}")
            if self.code_input.value:
                mock_event = {'new': self.code_input.value, 'old': self.code_input.value, 'name': 'value', 'type': 'change', 'owner': self.code_input}
                self.on_single_code_change(mock_event)
    
        def setup_callbacks(self):
            self.code_input.observe(self.on_single_code_change, names='value')
            self.multi_submit_button.on_click(self.on_multi_submit)
            self.export_button.on_click(self.on_export)
            self.clear_button.on_click(self.on_clear)
            self.test_historical_button.on_click(self.on_test_historical)
            self.date_format_toggle.observe(self._on_date_format_change, names='value')
    
        def format_confidence(self, confidence: float) -> str:
            try: conf_val = float(confidence)
            except (ValueError, TypeError): conf_val = 0.0
            if conf_val >= 0.85: return f'<span class="confidence-high">Very High ({conf_val:.0%})</span>'
            elif conf_val >= 0.70: return f'<span class="confidence-medium">High ({conf_val:.0%})</span>'
            elif conf_val >= 0.50: return f'<span class="confidence-low" style="color: #FF8C00;">Medium ({conf_val:.0%})</span>'
            else: return f'<span class="confidence-low">Low ({conf_val:.0%})</span>'
    
        def on_single_code_change(self, change: Dict[str, Any]):
            self.output.clear_output()
            code = change['new'].strip()
            if not code:
                with self.output: display(HTML("<p><i>Enter a batch code to see analysis.</i></p>"))
                return
    
            with self.output:
                valid, message, all_interpretations = self.validator.analyze_batch_code(code)
                html_output_parts = [f'<div class="batch-code-app">']
                if valid and all_interpretations:
                    html_output_parts.append(f'<h3>✅ Analysis Results for "<span class="result-info">{code}</span>" ({message})</h3><hr/>')
                    for i, result_dict in enumerate(all_interpretations, 1):
                        confidence_html = self.format_confidence(result_dict.get('confidence', 0.0))
                        prod_date_str = self._format_datetime_for_display(result_dict['production_date'])
                        expiry_date_str = self._format_datetime_for_display(result_dict['expiry_date'])
                        days_to_expiry = (result_dict['expiry_date'].date() - datetime.now().date()).days
                        div_status_class, text_status_class, expiry_status_text = self._get_expiry_status_info(days_to_expiry)
                        expiry_status_span = f'<span class="{text_status_class}">{expiry_status_text}</span>'
                        details_html_parts = []
                        if 'batch' in result_dict: details_html_parts.append(f'<strong>Batch:</strong> {result_dict["batch"]}')
                        if 'suffix' in result_dict: details_html_parts.append(f'<strong>Suffix:</strong> {result_dict["suffix"]}')
                        if 'prefix' in result_dict: details_html_parts.append(f'<strong>Prefix:</strong> {result_dict["prefix"]}')
                        if 'julian_day' in result_dict: details_html_parts.append(f'<strong>Julian Day:</strong> {result_dict["julian_day"]}')
                        if 'format_type' in result_dict: details_html_parts.append(f'<strong>Detected Format:</strong> {result_dict["format_type"]}')
                        details_html = "<br/>".join(d for d in details_html_parts if d)
                        html_output_parts.append(f"""
                        <div class="code-info {div_status_class}"> <!-- Applied new status class here -->
                            <h4>🔍 Interpretation {i}: {result_dict.get('format_name_source', 'Unknown Pattern')} ({confidence_html})</h4>
                            <p><i>Rule Message: {result_dict.get('parsing_message', 'N/A')}</i></p>
                            <p><strong>Production Date:</strong> {prod_date_str}</p>
                            <p><strong>Expiry Date:</strong> {expiry_date_str}</p>
                            <p><strong>Status:</strong> {expiry_status_span}</p>
                            <p>{details_html}</p>
                        </div>""")
                else:
                    html_output_parts.append(f"""
                    <h3 class="result-error">❌ Could not analyze '{code}'</h3><p><strong>Reason:</strong> {message}</p>
                    <p><strong>💡 Tips:</strong><ul><li>Ensure code is entered correctly.</li><li>Check Help tab for known formats.</li><li>Code might be too old, new, or use an unrecognized format.</li></ul></p>""")
                html_output_parts.append('</div>')
                display(HTML("".join(html_output_parts)))
    
        def on_multi_submit(self, button: widgets.Button):
            codes = [code.strip() for code in self.multi_code_input.value.split('\n') if code.strip()]
            if not codes:
                with self.output: self.output.clear_output(); display(HTML("<p class='result-error'>❌ No codes entered.</p>"))
                return
    
            self.progress.value = 0; self.progress.max = len(codes); self.progress.layout.visibility = 'visible'
            results_list_for_df = []
            self.output.clear_output()
            with self.output:
                display(HTML(f"<p>🔄 Processing {len(codes)} batch codes using {self.date_format_preference} date format for output...</p><hr/>"))
                processed_summaries = []
                for i, code in enumerate(codes):
                    self.progress.value = i + 1; self.progress.description = f"Processing {i+1}/{len(codes)}"
                    valid, message, interpretations = self.validator.analyze_batch_code(code)
                    if valid and interpretations:
                        top_interpretation = interpretations[0]
                        days_to_expiry = (top_interpretation['expiry_date'].date() - datetime.now().date()).days
                        _, _, expiry_status_text_desc = self._get_expiry_status_info(days_to_expiry)
                        prod_date_str = self._format_datetime_for_display(top_interpretation['production_date'], include_day_name=False)
                        exp_date_str = self._format_datetime_for_display(top_interpretation['expiry_date'], include_day_name=False)
                        details_parts = [f"Format: {top_interpretation.get('format_type', 'N/A')}", f"Confidence: {top_interpretation.get('confidence', 0.0):.0%}"]
                        if 'suffix' in top_interpretation: details_parts.append(f"Suffix: {top_interpretation['suffix']}")
                        results_list_for_df.append({'Code': code, 'Format': top_interpretation.get('format_type', 'N/A'), 'Production Date': prod_date_str, 'Expiry Date': exp_date_str, 'Days To Expiry': days_to_expiry, 'Expiry Status': expiry_status_text_desc, 'Confidence': f"{top_interpretation.get('confidence', 0.0):.2f}", 'Details': "; ".join(details_parts) + f" ({len(interpretations)} interp.)"})
                        prod_date_html_str = self._format_datetime_for_display(top_interpretation['production_date'])
                        exp_date_html_str = self._format_datetime_for_display(top_interpretation['expiry_date'])
                        processed_summaries.append(f'<p><span class="result-success">✅ {code}:</span> {top_interpretation.get("format_type", "Valid")} ({len(interpretations)} interp.) Prod: {prod_date_html_str}, Exp: {exp_date_html_str} <span class="{self._get_expiry_status_info(days_to_expiry)[1]}">({expiry_status_text_desc})</span></p>')
                    else:
                        results_list_for_df.append({'Code': code, 'Format': 'Unknown', 'Production Date': 'N/A', 'Expiry Date': 'N/A', 'Days To Expiry': None, 'Expiry Status': f'Invalid - {message}', 'Confidence': "0.00", 'Details': message})
                        processed_summaries.append(f'<p><span class="result-error">❌ {code}:</span> {message}</p>')
    
                display(HTML("".join(processed_summaries)))
                self.results_df = pd.DataFrame(results_list_for_df)
                df_display = self.results_df
                if 'Days To Expiry' in self.results_df.columns:
                    df_display = self.results_df.copy(); df_display['Days To Expiry'] = pd.to_numeric(df_display['Days To Expiry'], errors='coerce'); df_display = df_display.sort_values(by='Days To Expiry', ascending=True, na_position='last')
                display(HTML(f"<hr/><p>📊 Processing Complete! Found {len(self.results_df[self.results_df['Expiry Status'].str.startswith('Expires', na=False) | self.results_df['Expiry Status'].str.startswith('⚠️ Expired', na=False)])} codes with date info out of {len(codes)}.</p>"))
                if not df_display.empty:
                    display(HTML("<h4>📋 Results Preview (top 10, sorted by urgency):</h4>")); display(df_display.head(10))
                    if len(df_display) > 10: display(HTML(f"<p><i>... and {len(df_display) - 10} more rows. Use 'Export to CSV' for full results.</i></p>"))
            self.progress.layout.visibility = 'hidden'; self.progress.description = "Progress:"
    
        def on_export(self, button: widgets.Button):
            self.output.clear_output()
            with self.output:
                if self.results_df.empty:
                    display(HTML("<p class='result-error'>❌ No results to export.</p>")); logger.warning("Export attempt no data.")
                    return
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"batch_code_results_{timestamp}_{self.date_format_preference}.csv"
                    export_df = self.results_df.copy()
                    if 'Days To Expiry' in export_df.columns:
                        export_df['Days To Expiry'] = pd.to_numeric(export_df['Days To Expiry'], errors='coerce')
    
                    export_df.to_csv(filename, index=False)
                    logger.info(f"Results exported to {filename}, {len(export_df)} records. Date format: {self.date_format_preference}")
    
                    html_message = f"""
                    <div class='batch-code-app'>
                        <h4 class='result-success'>✅ Results exported!</h4>
                        <p><strong>Filename:</strong> {filename}</p>
                        <p><strong>Records:</strong> {len(export_df)}</p>
                    """
                    if IS_COLAB_ENV:
                        html_message += "<p>Your browser should start the download automatically. If not, check your browser's download permissions for this site, or find the file in Colab's file browser (folder icon on the left) and download manually.</p>"
                    html_message += "</div>"
                    display(HTML(html_message))
    
                    if IS_COLAB_ENV:
                        files.download(filename)
                    else:
                        display(FileLink(filename, result_html_prefix="📥 Download: "))
                except Exception as e:
                    logger.error(f"Export failed: {e}", exc_info=True)
                    display(HTML(f"<p class='result-error'>❌ Export failed: {str(e)}</p>"))
    
        def on_clear(self, button: widgets.Button):
            self.code_input.value = ''; self.multi_code_input.value = ''
            self.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Days To Expiry', 'Expiry Status', 'Confidence', 'Details'])
            self.output.clear_output(); logger.info("All inputs and results cleared.")
            with self.output: display(HTML("<p class='result-info'>🗑️ All data cleared successfully!</p>"))
    
        def on_test_historical(self, button: widgets.Button):
            self.output.clear_output()
            with self.output:
                display(HTML(f"<h3>🧪 Running Historical Pattern Tests (Date Format: {self.date_format_preference})...</h3><hr/>"))
                test_codes_info = []
                for pattern_key, pattern_data in self.validator.historical_patterns.items():
                    if 'examples' in pattern_data:
                        for example_code in pattern_data['examples']: test_codes_info.append({'code': example_code, 'source': pattern_key, 'type': 'Historical Example'})
                legacy_examples = [{'code': '1232401', 'source': 'DDDYYBB', 'type': 'Legacy Example'}, {'code': '24123AB', 'source': 'YYDDD+Suffix', 'type': 'Legacy Example'}, {'code': '010124', 'source': 'DDMMYY', 'type': 'Historical Example (ddmmyy_variants)'}]
                test_codes_info.extend(legacy_examples)
                seen_codes_for_test = set(); final_test_codes = []
                for item in test_codes_info:
                    if item['code'] not in seen_codes_for_test: final_test_codes.append(item); seen_codes_for_test.add(item['code'])
                if not final_test_codes: display(HTML("<p class='result-error'>No example codes found.</p>")); return
                display(HTML(f"<p>Testing {len(final_test_codes)} example codes:</p>"))
                test_results_html = ["<div class='batch-code-app'>"]
                for i, test_item in enumerate(final_test_codes):
                    code_to_test = test_item['code']; source_info = f"(Example from: {test_item['source']}, Type: {test_item['type']})"
                    valid, message, interpretations = self.validator.analyze_batch_code(code_to_test)
                    div_status_class_test = "status-good"
                    if valid and interpretations:
                        days_to_expiry_test = (interpretations[0]['expiry_date'].date() - datetime.now().date()).days
                        div_status_class_test, _, _ = self._get_expiry_status_info(days_to_expiry_test)
                    test_results_html.append(f"<div class='code-info {div_status_class_test}'><h4>Test Case {i+1}: Code '<code>{code_to_test}</code>' <small>{source_info}</small></h4>")
                    if valid and interpretations:
                        test_results_html.append(f"<p class='result-success'>✅ SUCCESS: Found {len(interpretations)} interpretation(s). Message: {message}</p>")
                        for j, interp in enumerate(interpretations, 1):
                            conf_html = self.format_confidence(interp.get('confidence',0))
                            prod_d = self._format_datetime_for_display(interp['production_date'])
                            exp_d = self._format_datetime_for_display(interp['expiry_date'])
                            days_to_exp_interp = (interp['expiry_date'].date() - datetime.now().date()).days
                            _, text_cls_interp, stat_text_interp = self._get_expiry_status_info(days_to_exp_interp)
                            test_results_html.append(f"<div style='padding-left: 15px; border-left: 2px solid #eee; margin-bottom: 5px;'><strong>Interpretation {j}:</strong> {interp.get('format_type', 'N/A')} ({conf_html})<br/>Prod: {prod_d}, Exp: {exp_d} <span class='{text_cls_interp}'>({stat_text_interp})</span><br/><i>Rule Msg: {interp.get('parsing_message', 'N/A')}</i></div>")
                    else: test_results_html.append(f"<p class='result-error'>❌ FAILED for '{code_to_test}': {message}</p>")
                    test_results_html.append("</div>")
                test_results_html.append("<hr/><p>🧪 Historical pattern testing complete!</p></div>")
                display(HTML("".join(test_results_html)))
    
        def display_gui(self):
            """Display the GUI."""
            display(self.main_container)
    
    if __name__ == "__main__":
        pass
    
    app = BatchCodeGUI()
    app.display_gui()
    st.success("✅ Batch code validation completed successfully!")

except Exception as e:
    st.error(f"❌ An error occurred: {e}")
