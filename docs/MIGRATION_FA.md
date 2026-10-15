# یکسان‌سازی نام در PyDara 0.6.0a2

نام پروژه در PyPI، پوشهٔ کد و import پایتون همگی `pydara` هستند.

```console
python -m pip install --upgrade pydara==0.6.0a2
```

```python
from pydara import tse
from pydara.tse import Client, AsyncClient
from pydara.tse.exceptions import PyDaraError

sample = tse.load_sample()
matches = tse.assets(symbol="فولاد", on_multiple="all")
```

در همهٔ برنامه‌ها و Notebookها از import جدید استفاده کنید و Kernel را Restart کنید.
فعلاً فقط `pydara.tse` پیاده‌سازی شده است؛ ماژول‌های تحلیل و ML هنوز عرضه نمی‌شوند.

## داده و ذخیره‌سازی

متادیتای خروجی‌های جدید در `frame.attrs['pydara']` است.
قالب آرشیو جدید `pydara-frame` و نام فایل کش جدید `pydara.sqlite3` است.
مسیر پیش‌فرض برای نصب تازه در پوشهٔ دادهٔ برنامهٔ `pydara` قرار می‌گیرد.
اگر کش قبلی موجود باشد، برای حفظ دسترسی به داده‌ها خوانده می‌شود؛ فایل‌های کاربر حذف یا جابه‌جا نمی‌شوند.
خواندن آرشیوهای قدیمی نیز پشتیبانی می‌شود و نام متادیتای خروجی به نام جدید تبدیل می‌شود.
نام‌های قدیمی فقط در مسیرهای سازگاری با داده‌های ذخیره‌شده باقی می‌مانند.

## ساخت

```console
python -m pip install build twine
python tools/build.py
python -m pytest -q
```
