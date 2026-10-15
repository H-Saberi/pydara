from datetime import date, datetime, timedelta
import pytest
from pydara.tse.dates import to_jalali, to_gregorian, parse_range
from pydara.tse.exceptions import InvalidArgumentError


@pytest.mark.parametrize('g,j',[
    ('2011-03-21','1390-01-01'),('2012-03-20','1391-01-01'),
    ('2016-04-11','1395-01-23'),('2020-03-20','1399-01-01'),
    ('2021-03-20','1399-12-30'),('2021-03-21','1400-01-01'),
    ('2024-03-20','1403-01-01'),('2025-03-20','1403-12-30'),
    ('2025-03-21','1404-01-01'),('2026-10-13','1405-07-21'),
])
def test_known_dates(g,j):
    assert to_jalali(g)==j
    assert to_gregorian(j)==date.fromisoformat(g)


@pytest.mark.parametrize('value',['1402-12-30','1403-13-01','1403-00-01','1403-07-31',
    '1403-01-00','1403/01/01','14030101','1403-1-1','1600-01-01','1199-01-01',None,True,14030101])
def test_invalid_jalali(value):
    with pytest.raises(InvalidArgumentError):to_gregorian(value)


def test_persian_arabic_numerals_and_date_objects():
    assert to_gregorian('\u06f1\u06f4\u06f0\u06f3-\u06f0\u06f1-\u06f0\u06f1')==date(2024,3,20)
    assert to_gregorian('\u0661\u0664\u0660\u0663-\u0660\u0661-\u0660\u0661')==date(2024,3,20)
    assert to_gregorian(date(2024,3,20))==date(2024,3,20)
    with pytest.raises(InvalidArgumentError):to_jalali(datetime(2024,3,20))
    with pytest.raises(InvalidArgumentError):parse_range('2024-04-01','2024-03-01')
    with pytest.raises(InvalidArgumentError):parse_range('1500-01-01',None)


def test_calendar_roundtrip_financial_range():
    d=date(1900,1,1)
    end=date(2101,1,1)
    while d < end:
        assert to_gregorian(to_jalali(d))==d
        d+=timedelta(days=7)
