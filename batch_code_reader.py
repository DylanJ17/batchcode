"""
Philip Kingsley Batch Code Reader
A professional Streamlit application for analyzing batch codes
"""

import streamlit as st
from datetime import datetime, timedelta
import calendar
import pandas as pd
import re
from typing import List, Tuple, Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Batch Code Reader",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    :root {
        --primary-color: #0078D7;
        --success-color: #28a745;
        --warning-color: #fd7e14;
        --danger-color: #dc3545;
        --info-color: #17a2b8;
    }
    
    .main {
        background-color: #f8f9fa;
    }
    
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 16px;
        font-weight: 500;
    }
    
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid var(--primary-color);
    }
    
    .result-success {
        color: var(--success-color);
        font-weight: bold;
    }
    
    .result-error {
        color: var(--danger-color);
        font-weight: bold;
    }
    
    .result-warning {
        color: var(--warning-color);
        font-weight: bold;
    }
    
    .result-info {
        color: var(--info-color);
        font-weight: bold;
    }
    
    .status-expired {
        background-color: #ffebee;
        border-left: 4px solid #c62828;
    }
    
    .status-expires-soon-30 {
        background-color: #fff3e0;
        border-left: 4px solid #ef6c00;
    }
    
    .status-expires-soon-90 {
        background-color: #fffde7;
        border-left: 4px solid #fbc02d;
    }
    
    .status-good {
        background-color: #e8f5e9;
        border-left: 4px solid #388e3c;
    }
    
    hr {
        margin: 20px 0;
        border-color: #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)


class BatchCodeValidator:
    """Enhanced batch code validator trained on historical Philip Kingsley data."""

    def __init__(self):
        self.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Status', 'Confidence'])
        self.historical_patterns = self._load_historical_patterns()
        self.current_year = datetime.now().year

    def _load_historical_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load and analyze historical batch code patterns."""
        return {
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
                'description': 'Letter prefix + ambiguous date + suffix',
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
        """Add years to a date, handling leap year edge cases."""
        try:
            return date.replace(year=date.year + years)
        except ValueError:
            if date.month == 2 and date.day == 29:
                return date.replace(month=2, day=28, year=date.year + years)
            raise

    def is_valid_expiry(self, expiry_date: datetime) -> bool:
        """Check if expiry date is within a valid range (2015 up to 3 years from today)."""
        today = datetime.now().date()
        max_expiry_dt = datetime(today.year + 3, today.month, today.day)
        min_expiry_dt = datetime(2015, 1, 1)
        return min_expiry_dt.date() <= expiry_date.date() <= max_expiry_dt.date()

    @staticmethod
    def _resolve_two_digit_year(yy: int) -> int:
        """Resolves a two-digit year to a four-digit year."""
        if not (0 <= yy <= 99):
            raise ValueError("Two-digit year 'yy' must be between 0 and 99.")
        current_century_start = (datetime.now().year // 100) * 100
        if yy < 50:
            return current_century_start + yy
        else:
            return (current_century_start - 100) + yy

    def parse_date_variants(self, part1: int, part2: int, yy: int) -> List[datetime]:
        """Try different date interpretations and return valid ones."""
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
        max_prod_date_candidate = current_dt + timedelta(days=90)

        for year_val in valid_prod_years:
            try:
                if 1 <= part1 <= 31 and 1 <= part2 <= 12:
                    dt = datetime(year_val, part2, part1)
                    if dt <= max_prod_date_candidate:
                        candidates.append(dt)
            except ValueError:
                pass
            
            try:
                if 1 <= part1 <= 12 and 1 <= part2 <= 31:
                    dt = datetime(year_val, part1, part2)
                    if dt not in candidates and dt <= max_prod_date_candidate:
                        candidates.append(dt)
            except ValueError:
                pass

            if 1 <= part1 <= 12:
                try:
                    last_day = calendar.monthrange(year_val, part1)[1]
                    dt = datetime(year_val, part1, last_day)
                    if dt not in candidates and dt <= max_prod_date_candidate:
                        candidates.append(dt)
                except ValueError:
                    pass

        unique_candidates = []
        seen = set()
        for c in sorted(candidates):
            if c not in seen:
                unique_candidates.append(c)
                seen.add(c)
        return unique_candidates

    def _process_parsed_dates(self, code_part_for_msg: str, prod_date_candidates: List[datetime], 
                             suffix: Optional[str] = "", base_confidence: float = 0.8, 
                             format_desc_prefix: str = "") -> List[Dict]:
        results = []
        if not prod_date_candidates:
            return []
        
        for prod_date in prod_date_candidates:
            expiry_date = self.add_years(prod_date, 3)
            if self.is_valid_expiry(expiry_date):
                res_dict = {
                    'production_date': prod_date,
                    'expiry_date': expiry_date,
                    'confidence': base_confidence,
                    'format_type': format_desc_prefix if format_desc_prefix else "Parsed Date"
                }
                if suffix:
                    res_dict['suffix'] = suffix
                results.append(res_dict)
        return results

    def validate_yddd_bb(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: YDDD BB (e.g., 500903)."""
        pattern_info = self.historical_patterns.get('yddd_bb', {})
        match = re.match(pattern_info.get('pattern', '^$'), code)
        if not match:
            return False, "Not YDDD BB pattern", []

        try:
            y_str, ddd_str, bb_str = match.groups()
            y_digit, ddd = int(y_str), int(ddd_str)
            current_year = datetime.now().year
            year_candidate_1 = (current_year // 10) * 10 + y_digit
            if year_candidate_1 > current_year:
                year = year_candidate_1 - 10
            else:
                year = year_candidate_1

            if not (2015 <= year <= (current_year + 1)):
                return False, f"Resolved year {year} is out of valid range", []

            prod_date = self.julian_to_date(year, ddd)
            expiry_date = self.add_years(prod_date, 3)

            if self.is_valid_expiry(expiry_date):
                return True, f"YDDD BB (Year: {year}, Julian: {ddd}, Batch: {bb_str})", [{
                    'production_date': prod_date,
                    'expiry_date': expiry_date,
                    'julian_day': ddd,
                    'batch': bb_str,
                    'confidence': 0.98,
                    'format_type': 'YDDD BB'
                }]
        except (ValueError, OverflowError):
            pass

        return False, f"Invalid data for YDDD BB pattern", []

    def validate_historical_pattern_1(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: ddmmyyyy variants"""
        pattern_info = self.historical_patterns['ddmmyyyy_variants']
        match = re.match(pattern_info['pattern'], code)
        if not match:
            return False, "Not historical pattern 1", []
        
        try:
            day_str, month_str, yy_str, suffix_str = match.groups()
            day, month, yy = int(day_str), int(month_str), int(yy_str)
            candidates = self.parse_date_variants(day, month, yy)
            results = self._process_parsed_dates(f"{day_str}-{month_str}-{yy_str}", candidates, suffix_str, 0.9, "DD/MM/YY or MM/DD/YY")
            if results:
                for r in results:
                    if r['production_date'].day == day and r['production_date'].month == month:
                        r['format_type'] = "DD/MM/YY + suffix"
                    elif r['production_date'].month == day and r['production_date'].day == month:
                        r['format_type'] = "MM/DD/YY + suffix"
                    else:
                        r['format_type'] = "Parsed Date (MM/YY?) + suffix"
                return True, f"Historical Pattern 1 - Suffix: {suffix_str}", results
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data historical pattern 1", []

    def validate_historical_pattern_2(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: ddmmyy or mmddyy"""
        pattern_info = self.historical_patterns['ddmmyy_variants']
        match = re.match(pattern_info['pattern'], code)
        if not match:
            return False, "Not historical pattern 2", []
        
        try:
            p1_str, p2_str, yy_str = match.groups()
            part1, part2, yy = int(p1_str), int(p2_str), int(yy_str)
            candidates = self.parse_date_variants(part1, part2, yy)
            results = self._process_parsed_dates(f"{p1_str}-{p2_str}-{yy_str}", candidates, base_confidence=0.85, format_desc_prefix="DD/MM/YY or MM/DD/YY")
            if results:
                for r in results:
                    if r['production_date'].day == part1 and r['production_date'].month == part2:
                        r['format_type'] = "DD/MM/YY"
                    elif r['production_date'].month == part1 and r['production_date'].day == part2:
                        r['format_type'] = "MM/DD/YY"
                    else:
                        r['format_type'] = "MM/YY (End of Month)"
                return True, f"Historical Pattern 2", results
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data historical pattern 2", []

    def validate_historical_pattern_3(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: Julian day + year + suffix"""
        pattern_info = self.historical_patterns['julian_with_suffix']
        match = re.match(pattern_info['pattern'], code)
        if not match:
            return False, "Not historical pattern 3", []
        
        try:
            ddd_str, yy_str, suffix_str = match.groups()
            ddd, yy = int(ddd_str), int(yy_str)
            year = self._resolve_two_digit_year(yy)
            if not (2015 <= year <= (self.current_year + 1)):
                return False, f"Year {year} out of range", []
            
            prod_date = self.julian_to_date(year, ddd)
            expiry_date = self.add_years(prod_date, 3)
            if self.is_valid_expiry(expiry_date):
                return True, f"Historical Pattern 3 (Julian {ddd}/{year} + suffix: {suffix_str})", [{
                    'production_date': prod_date,
                    'expiry_date': expiry_date,
                    'julian_day': ddd,
                    'suffix': suffix_str,
                    'confidence': 0.95,
                    'format_type': 'Julian DDDYY + Suffix'
                }]
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data historical pattern 3", []

    def validate_historical_pattern_4(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: Date digits + alphabetic suffix"""
        pattern_info = self.historical_patterns['mixed_alpha']
        match = re.match(pattern_info['pattern'], code)
        if not match:
            return False, "Not historical pattern 4", []
        
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
                        if self.is_valid_expiry(expiry_date):
                            final_results.append({
                                'production_date': prod_date,
                                'expiry_date': expiry_date,
                                'julian_day': ddd,
                                'alpha_suffix': alpha_suffix,
                                'confidence': 0.9,
                                'format_type': 'Julian DDDYY + Alpha Suffix'
                            })
                    except ValueError:
                        pass
            
            elif len(date_part_str) == 4:
                p1 = int(date_part_str[:2])
                p2 = int(date_part_str[2:4])
                candidates = self.parse_date_variants(p1, p2, yy)
                processed = self._process_parsed_dates(f"{date_part_str}-{yy_str}", candidates, alpha_suffix, 0.85, "DDMMYY/MMDDYY + Alpha")
                for r_item in processed:
                    r_item['alpha_suffix'] = alpha_suffix
                final_results.extend(processed)
            
            if final_results:
                return True, f"Historical Pattern 4 - Alpha Suffix: {alpha_suffix}", final_results
        
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data historical pattern 4", []

    def validate_prefix_yymm_suffix(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: Prefix + YY + MM + Suffix"""
        pattern_info = self.historical_patterns.get('prefix_yymm_suffix', {})
        match = re.match(pattern_info.get('pattern', '^$'), code)
        if not match:
            return False, "Not Prefix-YYMM-Suffix pattern", []
        
        try:
            prefix_str, yy_str, mm_str, suffix_str = match.groups()
            yy, mm = int(yy_str), int(mm_str)
            if not (1 <= mm <= 12):
                return False, f"Invalid month '{mm_str}'", []
            
            year = self._resolve_two_digit_year(yy)
            if not (2015 <= year <= (self.current_year + 1)):
                return False, f"Year {year} out of range", []
            
            last_day_of_month = calendar.monthrange(year, mm)[1]
            prod_date = datetime(year, mm, last_day_of_month)
            expiry_date = self.add_years(prod_date, 3)
            
            if self.is_valid_expiry(expiry_date):
                return True, f"Prefix-YYMM-Suffix (Prefix: {prefix_str}, Date: {mm:02d}/{year}, Suffix: {suffix_str})", [{
                    'production_date': prod_date,
                    'expiry_date': expiry_date,
                    'prefix': prefix_str,
                    'suffix': suffix_str,
                    'confidence': 0.95,
                    'format_type': 'Prefix-YYMM-Suffix'
                }]
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data for Prefix-YYMM-Suffix", []

    def validate_special_prefix(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Pattern: Special formats like H1619A"""
        pattern_info = self.historical_patterns.get('special_prefix', {})
        match = re.match(pattern_info.get('pattern', '^$'), code)
        if not match:
            return False, "Not special_prefix pattern", []
        
        final_results = []
        try:
            prefix_char, date_digits_str, suffix_str = match.groups()
            if len(date_digits_str) == 4:
                p1 = int(date_digits_str[:2])
                p2_or_yy = int(date_digits_str[2:4])
                year_mmyy = self._resolve_two_digit_year(p2_or_yy)
                
                if 1 <= p1 <= 12 and (2015 <= year_mmyy <= self.current_year + 1):
                    try:
                        prod_dt_mmyy = datetime(year_mmyy, p1, calendar.monthrange(year_mmyy, p1)[1])
                        if prod_dt_mmyy <= (datetime.now() + timedelta(days=90)):
                            expiry_dt_mmyy = self.add_years(prod_dt_mmyy, 3)
                            if self.is_valid_expiry(expiry_dt_mmyy):
                                final_results.append({
                                    'production_date': prod_dt_mmyy,
                                    'expiry_date': expiry_dt_mmyy,
                                    'prefix': prefix_char,
                                    'suffix': suffix_str,
                                    'confidence': 0.75,
                                    'format_type': f"Special Prefix ({prefix_char}) + MMYY"
                                })
                    except ValueError:
                        pass
            
            if final_results:
                unique_final_results = []
                seen_dates = set()
                for res_u in sorted(final_results, key=lambda x: x['production_date']):
                    if res_u['production_date'] not in seen_dates:
                        unique_final_results.append(res_u)
                        seen_dates.add(res_u['production_date'])
                
                if unique_final_results:
                    return True, f"Special Prefix", unique_final_results
        
        except (ValueError, OverflowError):
            pass
        
        return False, f"Invalid data for special_prefix", []

    def validate_legacy_formats(self, code: str) -> Tuple[bool, str, List[dict]]:
        """Legacy validation for backward compatibility."""
        results = []
        current_year_val = self.current_year
        
        if len(code) == 7 and code.isdigit():
            try:
                ddd, yy, batch_suffix = int(code[:3]), int(code[3:5]), code[5:7]
                year = self._resolve_two_digit_year(yy)
                if 2015 <= year <= (current_year_val + 1):
                    prod_date = self.julian_to_date(year, ddd)
                    expiry_date = self.add_years(prod_date, 3)
                    if self.is_valid_expiry(expiry_date):
                        results.append({
                            'production_date': prod_date,
                            'expiry_date': expiry_date,
                            'batch': batch_suffix,
                            'confidence': 0.8,
                            'format_type': 'Legacy DDDYYBB (Julian)'
                        })
            except (ValueError, OverflowError):
                pass
        
        if len(code) >= 5 and code[:5].isdigit():
            try:
                yy, ddd = int(code[:2]), int(code[2:5])
                suffix_val = code[5:] if len(code) > 5 else ""
                year = self._resolve_two_digit_year(yy)
                if 2015 <= year <= (current_year_val + 1):
                    prod_date = self.julian_to_date(year, ddd)
                    expiry_date = self.add_years(prod_date, 3)
                    if self.is_valid_expiry(expiry_date):
                        is_dup = any(r['format_type'] == 'Legacy DDDYYBB (Julian)' and r['production_date'] == prod_date for r in results) if len(code) == 7 else False
                        if not is_dup:
                            results.append({
                                'production_date': prod_date,
                                'expiry_date': expiry_date,
                                'suffix': suffix_val,
                                'confidence': 0.8,
                                'format_type': 'Legacy YYDDD (Julian)' + (' + Suffix' if suffix_val else '')
                            })
            except (ValueError, OverflowError):
                pass
        
        if results:
            return True, "Legacy Format Match", results
        return False, "No legacy format match", []

    def analyze_batch_code(self, code: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Comprehensive batch code analysis."""
        code_orig = code.strip()
        cleaned_code = re.sub(r'[-_./\\\s]', '', code_orig.upper())
        
        if not cleaned_code:
            return False, "Empty code", []

        validators = [
            ('YDDD-BB', self.validate_yddd_bb),
            ('Prefix-YYMM-Suffix', self.validate_prefix_yymm_suffix),
            ('Julian DDDYY+Suffix', self.validate_historical_pattern_3),
            ('DDMMYY+Suffix', self.validate_historical_pattern_1),
            ('Date+Alpha Suffix', self.validate_historical_pattern_4),
            ('DDMMYY or MMDDYY', self.validate_historical_pattern_2),
            ('Legacy Formats', self.validate_legacy_formats),
            ('Special Prefix', self.validate_special_prefix),
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
            except Exception as e:
                logger.error(f"Exception {f_name_prefix}: {e}")

        if all_interpretations:
            has_yddd = any(i.get('format_type') == 'YDDD BB' for i in all_interpretations)
            has_dddyy = any(i.get('format_type') in ('Julian DDDYY + Suffix', 'Julian DDDYY + Alpha Suffix', 'Legacy DDDYYBB (Julian)') for i in all_interpretations)
            
            if has_yddd and has_dddyy:
                all_interpretations = [i for i in all_interpretations if i.get('format_type') != 'YDDD BB']

            unique_interpretations_final = []
            seen_keys = set()
            for interp in sorted(all_interpretations, key=lambda x: x.get('confidence', 0.0), reverse=True):
                key_tuple = (
                    interp['production_date'].toordinal(),
                    interp['expiry_date'].toordinal(),
                    interp.get('format_type', ''),
                    interp.get('suffix', ''),
                    interp.get('batch', ''),
                    interp.get('prefix', '')
                )
                if key_tuple not in seen_keys:
                    unique_interpretations_final.append(interp)
                    seen_keys.add(key_tuple)
            
            if not unique_interpretations_final:
                return False, "No valid interpretations after filtering", []
            
            unique_interpretations_final.sort(key=lambda x: x.get('confidence', 0.0), reverse=True)
            num_found = len(unique_interpretations_final)
            return True, f"Found {num_found} valid interpretation{'s' if num_found > 1 else ''}", unique_interpretations_final
        
        return False, "No valid date patterns found", []


# Initialize session state
if 'validator' not in st.session_state:
    st.session_state.validator = BatchCodeValidator()

if 'results_df' not in st.session_state:
    st.session_state.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Days To Expiry', 'Expiry Status', 'Confidence', 'Details'])

if 'date_format' not in st.session_state:
    st.session_state.date_format = 'UK'


def format_datetime(dt: datetime, include_day_name: bool = True) -> str:
    """Format datetime based on preference."""
    if st.session_state.date_format == 'US':
        fmt = '%m/%d/%Y'
    else:
        fmt = '%d/%m/%Y'
    
    if include_day_name:
        return dt.strftime(f"{fmt} (%A)")
    else:
        return dt.strftime(fmt)


def get_expiry_status(days_to_expiry: int) -> Tuple[str, str]:
    """Get expiry status and CSS class."""
    if days_to_expiry < 0:
        return f"⚠️ Expired {abs(days_to_expiry)} days ago", "status-expired"
    elif days_to_expiry <= 30:
        return f"❗ Expires in {days_to_expiry} days (Critical)", "status-expires-soon-30"
    elif days_to_expiry <= 90:
        return f"⏰ Expires in {days_to_expiry} days (Soon)", "status-expires-soon-90"
    else:
        return f"✅ Expires in {days_to_expiry} days (Good)", "status-good"


def format_confidence(confidence: float) -> str:
    """Format confidence with color."""
    if confidence >= 0.85:
        return f"🟢 Very High ({confidence:.0%})"
    elif confidence >= 0.70:
        return f"🟡 High ({confidence:.0%})"
    elif confidence >= 0.50:
        return f"🟠 Medium ({confidence:.0%})"
    else:
        return f"🔴 Low ({confidence:.0%})"


# Main app layout
st.markdown("# 📦 Philip Kingsley Batch Code Reader")
st.markdown("Professional batch code analysis with historical pattern matching")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state.date_format = st.radio(
        "Date Display Format",
        options=["UK (DD/MM/YY)", "US (MM/DD/YY)"],
        format_func=lambda x: x,
        index=0 if st.session_state.date_format == 'UK' else 1,
        key="date_format_radio"
    )
    st.session_state.date_format = st.session_state.date_format_radio.split()[0]
    
    st.divider()
    st.subheader("📚 Supported Patterns")
    with st.expander("View All Patterns"):
        for name, info in st.session_state.validator.historical_patterns.items():
            st.markdown(f"**{name.replace('_', ' ').title()}**")
            st.caption(info['description'])
            st.caption(f"Examples: {', '.join(info['examples'])}")


# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Single Code", "📊 Batch Process", "⚙️ Utilities", "📚 Help"])

# Tab 1: Single Code Analysis
with tab1:
    st.subheader("Analyze a Single Batch Code")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        code_input = st.text_input(
            "Enter batch code",
            placeholder="e.g., 27124128, 17924AW, 500903",
            label_visibility="collapsed"
        )
    
    with col2:
        analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")
    
    if analyze_btn or code_input:
        if code_input:
            valid, message, interpretations = st.session_state.validator.analyze_batch_code(code_input)
            
            if valid and interpretations:
                st.success(f"✅ {message}")
                
                for i, result in enumerate(interpretations, 1):
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([1, 2, 2])
                        
                        with col1:
                            st.metric("Format", result.get('format_type', 'N/A')[:20])
                        
                        with col2:
                            conf = format_confidence(result.get('confidence', 0))
                            st.markdown(conf)
                        
                        with col3:
                            days_to_exp = (result['expiry_date'].date() - datetime.now().date()).days
                            status_text, _ = get_expiry_status(days_to_exp)
                            st.markdown(status_text)
                        
                        st.divider()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Production Date:** {format_datetime(result['production_date'])}")
                        with col2:
                            st.write(f"**Expiry Date:** {format_datetime(result['expiry_date'])}")
                        
                        # Additional details
                        details = []
                        if 'batch' in result:
                            details.append(f"Batch: {result['batch']}")
                        if 'suffix' in result:
                            details.append(f"Suffix: {result['suffix']}")
                        if 'prefix' in result:
                            details.append(f"Prefix: {result['prefix']}")
                        if 'julian_day' in result:
                            details.append(f"Julian Day: {result['julian_day']}")
                        
                        if details:
                            st.caption(" | ".join(details))
                        
                        if i < len(interpretations):
                            st.divider()
            else:
                st.error(f"❌ Could not analyze code: {message}")
                st.info("💡 Try checking the Help tab for supported formats or ensure the code is entered correctly.")

# Tab 2: Batch Processing
with tab2:
    st.subheader("Process Multiple Batch Codes")
    
    codes_text = st.text_area(
        "Enter batch codes (one per line)",
        placeholder="27124128\n17924AW\n500903",
        height=200,
        label_visibility="collapsed"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        process_btn = st.button("🚀 Process All", use_container_width=True, type="primary")
    with col2:
        clear_btn = st.button("🗑️ Clear", use_container_width=True)
    with col3:
        if not st.session_state.results_df.empty:
            csv = st.session_state.results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    if clear_btn:
        st.session_state.results_df = pd.DataFrame(columns=['Code', 'Format', 'Production Date', 'Expiry Date', 'Days To Expiry', 'Expiry Status', 'Confidence', 'Details'])
        st.rerun()
    
    if process_btn:
        codes = [c.strip().upper() for c in codes_text.split('\n') if c.strip()]
        
        if not codes:
            st.error("❌ No codes entered")
        else:
            progress_bar = st.progress(0)
            results_list = []
            
            for idx, code in enumerate(codes):
                progress_bar.progress((idx + 1) / len(codes))
                valid, message, interpretations = st.session_state.validator.analyze_batch_code(code)
                
                if valid and interpretations:
                    top = interpretations[0]
                    days_to_exp = (top['expiry_date'].date() - datetime.now().date()).days
                    status_text, _ = get_expiry_status(days_to_exp)
                    
                    details = [f"Format: {top.get('format_type', 'N/A')}"]
                    if 'suffix' in top:
                        details.append(f"Suffix: {top['suffix']}")
                    
                    results_list.append({
                        'Code': code,
                        'Format': top.get('format_type', 'N/A'),
                        'Production Date': format_datetime(top['production_date'], include_day_name=False),
                        'Expiry Date': format_datetime(top['expiry_date'], include_day_name=False),
                        'Days To Expiry': days_to_exp,
                        'Expiry Status': status_text,
                        'Confidence': f"{top.get('confidence', 0):.0%}",
                        'Details': "; ".join(details)
                    })
                else:
                    results_list.append({
                        'Code': code,
                        'Format': 'Unknown',
                        'Production Date': 'N/A',
                        'Expiry Date': 'N/A',
                        'Days To Expiry': None,
                        'Expiry Status': f'Invalid - {message}',
                        'Confidence': '0%',
                        'Details': message
                    })
            
            st.session_state.results_df = pd.DataFrame(results_list)
            
            st.success(f"✅ Processed {len(codes)} codes")
            
            # Show summary
            col1, col2, col3, col4 = st.columns(4)
            valid_count = len([r for r in results_list if r['Format'] != 'Unknown'])
            expired_count = len([r for r in results_list if r['Days To Expiry'] is not None and r['Days To Expiry'] < 0])
            critical_count = len([r for r in results_list if r['Days To Expiry'] is not None and 0 <= r['Days To Expiry'] <= 30])
            
            with col1:
                st.metric("Valid Codes", valid_count)
            with col2:
                st.metric("Expired", expired_count)
            with col3:
                st.metric("Critical (≤30 days)", critical_count)
            with col4:
                st.metric("Processing Date", datetime.now().strftime("%d/%m/%Y"))
            
            st.divider()
            
            # Display results table
            st.subheader("📋 Results")
            display_df = st.session_state.results_df.copy()
            if 'Days To Expiry' in display_df.columns:
                display_df = display_df.sort_values('Days To Expiry', ascending=True, na_position='last')
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)

# Tab 3: Utilities
with tab3:
    st.subheader("⚙️ Utilities & Testing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧪 Test All Patterns", use_container_width=True, type="secondary"):
            st.subheader("Pattern Test Results")
            
            test_codes = []
            for pattern_name, pattern_data in st.session_state.validator.historical_patterns.items():
                if 'examples' in pattern_data:
                    for example in pattern_data['examples']:
                        test_codes.append({'code': example, 'pattern': pattern_name})
            
            results_test = []
            for item in test_codes:
                valid, msg, interp = st.session_state.validator.analyze_batch_code(item['code'])
                results_test.append({
                    'Code': item['code'],
                    'Pattern': item['pattern'],
                    'Status': '✅ Valid' if valid else '❌ Failed',
                    'Message': msg
                })
            
            test_df = pd.DataFrame(results_test)
            st.dataframe(test_df, use_container_width=True, hide_index=True)
    
    with col2:
        if st.button("📊 Export Results", use_container_width=True, type="secondary"):
            if not st.session_state.results_df.empty:
                csv = st.session_state.results_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv,
                    file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("No results to export. Process some codes first.")

# Tab 4: Help
with tab4:
    st.subheader("📚 Help & Documentation")
    
    st.markdown("""
    ### How to Use This Application
    
    This batch code analyzer recognizes multiple Philip Kingsley batch code formats and determines:
    - **Production Date**: When the product was manufactured
    - **Expiry Date**: 3 years from the production date
    - **Status**: Whether the product is expired or upcoming
    
    ### Supported Formats
    """)
    
    for name, info in st.session_state.validator.historical_patterns.items():
        with st.expander(f"📌 {name.replace('_', ' ').upper()}"):
            st.write(f"**Description:** {info['description']}")
            st.write(f"**Examples:** {', '.join(info['examples'])}")
    
    st.divider()
    
    st.markdown("""
    ### Key Features
    
    - **Real-time Analysis**: Instant feedback for single codes
    - **Batch Processing**: Analyze multiple codes at once
    - **Multiple Interpretations**: Shows all possible matches with confidence scores
    - **Export Functionality**: Download results as CSV for further analysis
    - **Date Format Toggle**: Switch between UK (DD/MM/YY) and US (MM/DD/YY) formats
    - **Expiry Status Indicators**: Visual cues for expired, critical, and good status
    
    ### Confidence Scores
    
    - 🟢 **Very High (85%+)**: Most reliable interpretation
    - 🟡 **High (70-84%)**: Reliable but verify if critical
    - 🟠 **Medium (50-69%)**: Use with caution
    - 🔴 **Low (<50%)**: Verify before relying on result
    
    ### Date Range Rules
    
    - **Production Date**: 2015 to current year + 1 day
    - **Expiry Date**: Production date + 3 years (must fall within 2015 to current year + 3 years)
    
    ### Tips
    
    💡 If multiple interpretations appear, the first one (highest confidence) is usually correct
    
    💡 Some codes may be ambiguous (e.g., 052024 could be 05/20/24 or 05/02/24)
    
    💡 Historical patterns are based on known Philip Kingsley batch code formats
    """)


st.markdown("---")
st.markdown("<center>© 2024 Philip Kingsley Batch Code Reader | Built with Streamlit</center>", unsafe_allow_html=True)
