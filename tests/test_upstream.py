"""Regression checks first executed on unmodified upstream source."""
import io
import pandas as pd
from data_cleaning import DataCleaner
from utils import validate_file, get_dataset_info, save_dataframe
from streamlit.testing.v1 import AppTest


def test_upstream_cleaning_and_export(tmp_path):
    original = pd.DataFrame({'name': ['Ada', 'Bob', 'Cai'], 'amount': [10., None, 30.]})
    cleaner = DataCleaner(original)
    assert cleaner.identify_missing_values()['total_missing_cells'] == 1
    cleaner.fill_missing_values({'amount': {'strategy': 'median'}})
    cleaned = cleaner.get_cleaned_data()
    assert cleaned.amount.tolist() == [10., 20., 30.]
    assert original.amount.isna().sum() == 1
    assert cleaner.get_transformations_summary()['total_transformations'] >= 1
    target = tmp_path / 'cleaned.xlsx'
    assert save_dataframe(cleaned, str(target), 'excel')
    pd.testing.assert_frame_equal(pd.read_excel(target), cleaned, check_dtype=False)


def test_upstream_file_validation():
    assert validate_file(io.BytesIO(b'name,amount\nAda,10\n'))[0]
    assert not validate_file(io.BytesIO(b''))[0]
    assert get_dataset_info(pd.DataFrame({'id': ['01','02']}))['rows'] == 2


def test_upstream_page_starts():
    app = AppTest.from_file('src/app.py').run(timeout=40)
    assert not app.exception
    assert 'Dataset Cleaner' in app.title[0].value


def test_upstream_loaded_overview():
    app = AppTest.from_file('src/app.py').run(timeout=40)
    df = pd.DataFrame({'name': ['Ada', 'Bob', 'Cai'], 'amount': [10., None, 30.]})
    app.session_state['original_df'] = df
    app.session_state['cleaner'] = DataCleaner(df)
    app.session_state['file_info'] = {'filename': 'synthetic.csv', 'filesize': .001,
                                     'rows': 3, 'columns': 2, 'memory_usage': .001,
                                     'import_time': '2026-09-08'}
    app.run(timeout=40)
    assert not app.exception
