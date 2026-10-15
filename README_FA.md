# دارا — PyDara 0.7.3a6

نام نصب در PyPI برابر `pydara` و نام واردکردن در پایتون `pydara` است.

دارا کتابخانه‌ای ماژولار برای داده‌های مالی است. فعلاً فقط زیرماژول عمومی
`tse` پیاده‌سازی شده و قابلیت‌های نسخهٔ قبلی دادهٔ بورس را حفظ می‌کند.

## نصب

نسخهٔ این انتشار آزمایشی `0.7.3a6` است. نصب از PyPI:

```console
python -m pip install --upgrade pydara==0.7.3a6
```

برای نصب نسخهٔ فعلی از سورس GitHub:

```console
git clone https://github.com/H-Saberi/pydara.git
cd pydara
python -m pip install .
```

برای امکانات فایل و Notebook، به‌جای دستور آخر از `python -m pip install ".[files,notebook]"` استفاده کنید.
انتشار سورس در GitHub به معنی انتشار نسخهٔ تازه در PyPI نیست.

برای Excel، Parquet و Notebook:

```console
python -m pip install --upgrade "pydara[files,notebook]==0.7.3a6"
```

نصب محلی بستهٔ آماده: `python install.py` در محیط پایتون فعال.
پس از نصب یا ارتقا، Kernel ژوپیتر را Restart کنید.


## رابط عمومی یکپارچهٔ ۰٫۷٫۰

شش تابع اصلی برای استفادهٔ روزمره: `markets()` (خلاصه بازار)، `assets()` (نمادها و فیلترها)، `prices()` (قیمت و بازده روز)، `history()` (تاریخچه)، `traders()` (حقیقی/حقوقی) و `orders()` (بهترین سفارش‌ها و عمق گزارش‌شده). همهٔ خروجی‌ها DataFrame هستند و ستون‌های این شش رابط تک‌واژه‌ای هستند. اسامی طرح SQLite و کش تغییر نکرده‌اند.

```python
from pydara import tse

mkts = tse.markets(market=["TSE", "IFB"])
stocks = tse.assets(markets=mkts, industry_code="34")
prices = tse.prices(assets=stocks, on_error="collect")
daily = tse.prices(markets=mkts)  # همهٔ ردیف‌های مشاهده‌شدهٔ دیده‌بان
book = tse.orders(assets=stocks, depth=5)
client_data = tse.traders(assets=stocks)
historical = tse.history(assets=stocks, start="1403-01-01", end="1403-12-29")
```

شناسهٔ صنعت مثال صرفاً نمونهٔ ورودی است و انطباق آن با فهرست صنایع باید در منبع بررسی شود. فراخوانی‌ها به شبکه یا کش مجاز نیاز دارند؛ تصویر زندهٔ بورس تأیید نشده است.

ستون‌های `change`، `return` و `returnpct` به‌ترتیب اختلاف قیمت پایانی نسبت به قیمت مرجع قبل، بازده نسبی روز و درصد آن هستند. مثلاً `return=0.02` با `returnpct=2.0` متناظر است. این محاسبه بازده کل تعدیل‌شده بابت سود نقدی نیست. اگر قیمت مرجع معتبر نباشد هر دو مقدار خالی می‌مانند.

در `orders()` هر ردیف یک سمت از یک سطح سفارش است (`side="buy"` یا `"sell"`)؛ فقط پنج سطح گزارش‌شدهٔ برتر پشتیبانی می‌شود، نه دفتر کامل سفارش‌ها. دادهٔ تاریخی، به‌روزرسانی‌های گزارش‌شده است و عکس کامل از همهٔ لحظات بازار نیست.

در `markets()` داده‌های خلاصه، دیده‌بان، سفارش‌ها و حقیقی/حقوقی ممکن است در زمان‌های متفاوتی دریافت شده باشند؛ خطاها، وضعیت کش و اجزای سازنده در `DataFrame.attrs["pydara"]` ثبت می‌شوند. دادهٔ `assets()` بدون شناسه محدود به دیده‌بان مشاهده‌شده است، نه همهٔ نمادهای تاریخی.

برای نصب از فایل محلی پروژه در محیط مجازی فعال:

```console
python "G:\My progect\Python\TSE\Lib\pydara\install.py"
```


## شروع

```python
from pydara import tse

sample = tse.load_sample()  # دادهٔ مصنوعی، بدون شبکه
reference = tse.api_reference("assets")

# نیازمند اتصال شبکه یا کش مجاز
matches = tse.assets(symbol="فولاد", on_multiple="all")
history = tse.history("فولاد", start="1403-01-01", end="1403-12-30")
```

```python
from pydara.tse import Client, AsyncClient
from pydara.tse.exceptions import PyDaraError
```

## سیاست شناسایی ابزار

`on_multiple="all"` پیش‌فرض است و همهٔ نتایج منطبق را می‌دهد.
`"first"` اولین مورد با ترتیب منبع و `"error"` خطا در صورت ابهام را انتخاب می‌کند.
`on_conflict="error"` شروط داده‌شده را بررسی می‌کند؛ `"ins_code"` فقط با
کد صریح اجازهٔ اولویت دادن به کد را می‌دهد.

## مهاجرت و داده‌های قبلی

شرح کامل در [راهنمای مهاجرت](docs/MIGRATION_FA.md) است.
نام قبلی `pydara.data` به `pydara.tse` تبدیل شده است.
برای کمترین تغییر می‌توان `from pydara import tse as data` نوشت.
مسیر کش و قرارداد متادیتای فایل‌های ذخیره‌شده حفظ شده‌اند؛ پایگاه دادهٔ کاربر حذف نمی‌شود.

## دامنه و محدودیت

قیمت، تاریخچه، ابزارها، دیده‌بان، مشتریان، شاخص‌ها، عملیات گروهی، ذخیرهٔ SQLite
و خروجی فایل در `tse` در دسترس‌اند؛ پوشش هر خروجی به سرویس منبع وابسته است.
آزمون‌های مصنوعی، صحت یا دسترسی لحظه‌ای سرویس واقعی را تضمین نمی‌کنند.
ماژول‌های تحلیل و ML و داده‌های بیتکوین، دلار، طلا و بازارهای خارجی فعلاً در نقشهٔ راه هستند.

مرجع امضاها: [API_REFERENCE.md](docs/API_REFERENCE.md).
برای مشاهدهٔ مرجع بدون شبکه از `tse.api_reference()` استفاده کنید.

## راهنمای درون کد (Docstring)

در نسخهٔ 0.6.0a3 برای تمام توابع، متدها و کلاس‌های موجود Docstring ثبت شده است. در پایتون می‌توانید از `help(tse.Client.get_history)` یا در ژوپیتر از `tse.Client.get_history?` استفاده کنید. راهنمای قالب و محدودیت‌ها: `docs/DOCSTRING_GUIDE_FA.md`.

### تاریخچهٔ یک یا چند ابزار مالی (نسخهٔ 0.6.0a5)

```python
from pydara import tse

items = tse.assets(symbol="فولاد", on_multiple="all")
history_df = tse.history(items, start="1403-01-01", end="1403-12-29")

by_code = tse.history(ins_code="46348559193224090")
by_codes = tse.history(ins_code=["46348559193224090", "46348559193224090"])
identified = tse.assets(ins_code=["46348559193224090"])
by_list = tse.history(["فولاد", "فملی"], on_multiple="all", on_error="collect")
by_symbol = tse.history("فولاد", on_conflict="error")

print(by_list.attrs["pydara"]["errors"])
```

خروجی همواره یک DataFrame است؛ برای داده‌های چند نماد، کد ابزار و نماد در
ستون‌های خروجی حفظ می‌شود. سیاست‌های `on_multiple` و `on_conflict` مطابق
`assets()` هستند. نتیجهٔ آزمون آفلاین به‌معنای تأیید دادهٔ زندهٔ بورس نیست.

### تغییر API در 0.6.0a5

`instrument(ins_code=[...])` و `history(ins_code=[...])` فهرست شناسه‌ها را با ترتیب ثابت و بدون تکرار می‌پذیرند. نام `get_instrument` از رابط عمومی و کلاس‌های Client و AsyncClient حذف شده است؛ برای یافتن ابزار از `assets()` استفاده کنید. سیاست‌های `on_multiple` و `on_conflict` اعمال می‌شوند. شناسه‌های عددی اعشاری معتبر نیستند.

### دریافت قیمت گروهی (نسخهٔ 0.6.0a6)

```python
from pydara import tse
codes = ["46348559193224090"]  # کدهای نمونه؛ صحت زنده باید بررسی شود
quotes = tse.prices(ins_code=codes, on_multiple="all", on_conflict="error", on_error="collect")
print(quotes[["ins_code", "state", "is_active", "last_price", "closing_price", "fetched_at"]])
print(quotes.attrs["pydara"]["errors"])
```

همچنین می‌توان DataFrame خروجی `tse.assets()` را به `tse.prices(instrument=stocks)` داد.
`fetched_at` زمان دریافت داده است، نه لزوماً زمان آخرین معامله؛ `state` وضعیت معامله و `is_active` وضعیت ابزار هستند.


### راهنمای توابع در Jupyter (نسخهٔ 0.6.0a7)

```python
from pydara import tse
tse.price?
tse.history?
tse.instrument?
```

راهنما اکنون نوع، مقادیر پیش‌فرض، سیاست‌های مجاز و مثال توابع اصلی را شرح می‌دهد. برای مرجع کامل‌تر `docs/API_REFERENCE.md` را ببینید.


### داده‌های حقیقی و حقوقی با `traders()` (نسخهٔ 0.6.0a8)

```python
from pydara import tse
selected = tse.assets(ins_code=["46348559193224090"])
df = tse.traders(selected, start="1403-01-01", end="1403-12-29",
                 on_multiple="all", on_conflict="error", on_error="collect")
print(df.columns.tolist())
print(df.attrs["pydara"]["errors"])
```

نام ستون‌ها در خروجی جدید تک‌واژه‌ای‌اند، مانند `inscode`، `ibuycount` و `lbuyvolume`. پیشوند `i` به حقیقی و `l` به حقوقی اشاره دارد. نام‌های قدیمی در لایهٔ ذخیره‌سازی تغییر نکرده‌اند.


### رابط کوتاه و جمع 0.6.0a9

```python
from pydara import tse
all_observed = tse.assets()  # current watch only, NOT full historical registry
selected = tse.assets(market='TSE', industry_code='10')
quotes = tse.prices(assets=selected)
history = tse.history(assets=selected, start='1403-01-01', calendar='jalali')
buyers = tse.traders(assets=selected)
```

در این نسخهٔ آزمایشی نام‌های اصلی عمومی `assets`, `prices`, `history`, `traders` هستند.
خروجی این توابع نام ستون‌های تک‌واژه‌ای دارد (مانند `inscode`, `isactive`, `fetchedat`).
این نام‌گذاری فقط در خروجی عمومی است و نام‌های پایگاه داده و کش تغییر نکرده‌اند.
فیلتر `is_active` در صورتی که در فهرست جاری موجود نباشد، نیازمند بررسی تک‌تک ابزارهاست؛
بنابراین ممکن است دریافت فهرست بزرگ زمان‌بر باشد. فهرست جاری شامل همهٔ نمادهای تاریخی نیست.

### بازیابی انتخاب نماد و محدودیت درخواست‌های شبکه (0.7.1)

```python
from pydara import tse
single = tse.assets("فولاد")
by_symbol = tse.assets(symbol="فولاد")
by_code = tse.assets(ins_code="46348559193224090")
multiple = tse.assets(ins_code=["46348559193224090", "12345678901234567"])
all_observed = tse.assets()
```

شناسهٔ دوم در مثال بالا صرفاً نمونه است. فهرست نمادهای بدون فیلتر تنها داده‌های دیده‌بان مشاهده‌شده را شامل می‌شود.

خطای `RequestBudgetExceededError` نشان‌دهندهٔ تمام‌شدن بودجهٔ درخواست کلاینت است، نه نامعتبر بودن آرایهٔ `ins_code`. شمارندهٔ درخواست در کلاینت پیش‌فرض در طول نشست پایتون حفظ می‌شود. برای افزایش محدودیت **پیش از نخستین درخواست** و با رعایت نرخ درخواست منبع:

```python
from pydara import tse
from pydara.tse import ClientConfig, NetworkConfig
tse.configure(ClientConfig(network=NetworkConfig(request_budget=300)))
```

اگر کلاینت ایجاد شده است، ابتدا `tse.close()` را اجرا و گزارش آن را بررسی کنید، سپس `configure()` را فراخوانی کنید. بستن کلاینت و ساخت کلاینت جدید نباید به‌عنوان روشی برای دورزدن سیاست محدودیت سرویس استفاده شود. حفظ کش و استفادهٔ درست از آن، از درخواست‌های تکراری جلوگیری می‌کند.


PyDara 0.7.2: `tse.assets(markets=tse.markets("TSE"), symbol=["فولاد", "وبملت"])` selects multiple named assets. The former `market=` keyword is no longer accepted by `assets()`; use `markets=`. If a market identifier is unavailable in both provider watch formats, the call raises rather than guessing.


### 0.7.3a1: incomplete market labels
`assets(markets=...)` reads the observed watch without server-side market filtering, returns only rows whose market matches a verified label, and records excluded unknown labels in `DataFrame.attrs["pydara"]["unknown_market_rows_excluded"]`. It does not claim complete historical coverage.

### انتخاب بازار و دریافت دسته‌ای قیمت‌ها (نسخهٔ 0.7.3a2)

```python
from pydara import tse as ts
mrk = ts.markets("TSE")
ass = ts.assets(markets=mrk)
pr = ts.prices(assets=ass)
```

انتخاب بورس/فرابورس از پارامتر شناخته‌شدهٔ بازار در درخواست منبع استفاده می‌کند؛
اگر پاسخ JSON برای ردیف‌ها مقدار `flow` نداشته باشد، بازار بر اساس محدودسازی درخواست
منبع مشخص می‌شود و در `qualityflags` و فرادادهٔ `pydara` ثبت می‌گردد.
اگر خود پاسخ با محدودسازی درخواست تناقض داشته باشد، بازار ردیف نامشخص حدس زده نمی‌شود.
`assets()` بدون فیلتر، ردیف‌هایی را که بازارشان نامشخص است حفظ می‌کند.
فهرست دیده‌بان **فهرست کامل تاریخی نمادها نیست**.
در دریافت قیمت برای DataFrame بزرگ، PyDara ابتدا یک پاسخ گروهی دیده‌بان را می‌خواند
و فقط کدهای غایب را از مسیر تکی بررسی می‌کند. این روش همچنان به دسترسی و سیاست‌های
کش و تازه‌بودن داده بستگی دارد.

```python
print(ass.attrs.get("pydara", {}))
print(pr.attrs.get("pydara", {}))
```

دقت کنید که این قابلیت با دادهٔ زنده در محیط کاربر تأیید نشده است.


### اصلاحات 0.7.3a3
در `prices()` قیمت پایانی صفر یا نامعتبر برای محاسبه بازده به عنوان داده مفقود محسوب می‌شود؛ بنابراین `change`، `return` و `returnpct` در این حالت خالی می‌مانند. بازار معتبر خروجی `assets()` با تطبیق دقیق `inscode` حفظ می‌شود. تعارض بازار منبع قیمت با بازار ورودی جایگزین نمی‌شود و تعداد تعارض‌ها در `df.attrs["pydara"]` ثبت می‌شود.

### ریزمعاملات با `trades()` (نسخه 0.7.3a4)

```python
from pydara import tse
selected = tse.assets(symbol=["فولاد", "وبملت"])
result = tse.trades(assets=selected, start="1405-07-01", end="1405-07-22",
                    starttime="09:00:00", endtime="12:30:00")
display(result)
print(result.attrs["pydara"]["errors"])
```

در صورت حذف تاریخ‌ها، تاریخ امروز به وقت تهران برای ابتدا و انتها استفاده می‌شود. تاریخ‌های رشته‌ای شمسی یا میلادی با `calendar="auto"` شناسایی می‌شوند. زمان‌ها بر اساس ساعت محلی تهران تفسیر می‌شوند. نتیجه فقط معاملات گزارش‌شدهٔ منبع را نشان می‌دهد و کامل بودن تاریخچهٔ ریزمعاملات تضمین نشده است. محدودیت پیش‌فرض هر درخواست ۳۱ روز تقویمی است؛ `max_days` حداکثر تا ۳۶۶ قابل تنظیم است. برای بازه‌های طولانی، آن‌ها را به چند درخواست کوچک تقسیم کنید. مقادیر مفقود منبع پر نمی‌شوند.


## PyDara 0.7.3a5 — controlled trades batches
`tse.trades()` defaults to `maxassets=20` and `progress=True`. Increase `maxassets` explicitly for larger work. Supply `checkpoint="./trades_checkpoints"` to persist successful per-instrument responses as JSON; reusing the same path and request parameters resumes without fetching completed instruments. `workers=1` only: the synchronous Client is not thread-safe. Checkpoint files stay on the local machine and are not part of the distributed ZIP.

### تکمیل کنترل‌شدهٔ قیمت‌های ناقص

تابع `prices(assets=...)` برای ردیف دیده‌بانی که قیمت پایانی مثبت یا تاریخ معاملهٔ معتبر ندارد، درخواست تکمیلی مستقل را تا سقف پیش‌فرض ۲۰ نماد امتحان می‌کند. با `max_quote_fallback=0` این تکمیل غیرفعال می‌شود. افزایش سقف نیازمند مقدار صریح است؛ محدودیت شبکهٔ کلاینت همچنان اعمال می‌شود. نام نمادهای تکمیل‌نشده و درخواست‌های معوق در `df.attrs["pydara"]` ثبت می‌شوند. داده‌های صفر یا فاقد تاریخ به‌عنوان بازده معتبر نمایش داده نمی‌شوند.
