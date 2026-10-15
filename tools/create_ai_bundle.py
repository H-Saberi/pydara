"""Create a portable, verified AI handoff without environments or user data."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "handoff"


def prompt(version: str) -> str:
    return f"""این فایل فشرده، نسخهٔ کامل فعلی پروژهٔ من است. توسعه را از همین وضعیت ادامه بده.

نام پروژه، نام نصب در PyPI، پوشهٔ کد و namespace پایتون همگی pydara هستند.
نسخهٔ مبنای کد: {version}. وضعیت نصب و انتشار تأییدشده را از AI_VERIFICATION.json بخوان؛
ساخت یک فایل ZIP را به معنی انتشار یا نصب همان نسخه فرض نکن.
مسیر صحیح استفاده:
    from pydara import tse
    import pydara.tse
نام‌های قبلی را به importها، بسته‌بندی یا مثال‌های جدید برنگردان.

ابتدا 01_PROJECT_GUIDE_FA.txt، AI_VERIFICATION.json، pyproject.toml،
src/pydara/__init__.py، README_FA.md، docs/API_REFERENCE.md و آزمون‌های مرتبط را بخوان.
سپس متناسب با درخواست من، کد واقعی و آزمون‌ها را بررسی کن؛ وجود توضیح یا نقشهٔ راه
را به معنی پیاده‌سازی یا تأیید سرویس واقعی نگیر.

فعلاً تنها زیرماژول عمومی pydara.tse پیاده‌سازی شده است. هدف آینده، افزودن ماژول‌های
داده برای رمزارز، دلار و ارز، طلا و بازارهای خارجی و سپس تحلیل و ML است.
هیچ‌یک از این ماژول‌های آینده را بدون درخواست من، پیاده‌شده معرفی یا ایجاد نکن.

قابلیت‌های فعلی دادهٔ بورس، کلاینت همگام و ناهمگام، خروجی Pandas، شناسایی ابزار،
قیمت و تاریخچه، داده‌های بازار، دریافت گروهی و checkpoint، کش و SQLite و خروجی فایل
را حفظ کن. سیاست‌های on_multiple و on_conflict و تفاوت دادهٔ تازه، کش و آفلاین
نباید ناخواسته تغییر کنند. دادهٔ مصنوعی را به‌عنوان دادهٔ واقعی نمایش نده.

نام‌های قدیمی که در مسیر خواندن کش، آرشیو یا طرح SQLite دیده می‌شوند، برای سازگاری
داده‌های قبلی‌اند؛ وابستگی به کتابخانهٔ قدیمی نیستند. آنها را با جایگزینی سراسری
و بدون بررسی تغییر نده. داده، پایگاه، کش و محیط پایتون کاربر را حذف نکن.

در نسخه‌های بعدی، شمارهٔ نسخه را هماهنگ در pyproject.toml و src/pydara/__init__.py
به‌روز کن؛ نام پروژه و import را تغییر نده. Wheel و BUNDLE.json و checksumها،
مرجع API، مثال‌ها و یادداشت تغییرات را مطابق نتیجهٔ نهایی بازسازی کن.
نسخهٔ منتشرشدهٔ PyPI قابل جایگزینی نیست؛ برای انتشار بعدی شمارهٔ جدید لازم است.
انتشار یا حذف در PyPI را فقط در چارچوب درخواست صریح من انجام بده.
هیچ توکن، رمز، دادهٔ شخصی، محیط نصب‌شده یا کشی را در فایل تحویلی قرار نده.

این بستهٔ کد، wheelhouse کاملاً آفلاین نیست. وابستگی‌های پایتون ممکن است نیازمند دانلود باشند.
پس از تغییر، آزمون‌های متناسب و نصب Wheel در محیط جداگانه را بررسی کن و نتیجه و
محدودیت‌های واقعی را گزارش بده. موفقیت آزمون مصنوعی، تأیید دادهٔ زنده یا همهٔ نسخه‌های Python نیست.

در اولین پاسخ، نسخه و namespace تشخیص‌داده‌شده و بخش‌های مرتبط با درخواست جدیدم
را کوتاه تأیید کن؛ سپس کار را انجام بده. اگر هنوز تغییر مشخصی درخواست نکرده‌ام،
فقط دریافت وضعیت پروژه را تأیید کن و منتظر شرح تغییر بمان.
"""


def guide(version: str) -> str:
    return f"""راهنمای تحویل پروژهٔ PyDara — نسخهٔ مبنا {version}

۱. هویت پروژه
نام توزیع در PyPI: pydara
namespace و پوشهٔ کد: pydara و src/pydara
تنها زیرماژول عمومی فعلی: pydara.tse
استثناها: pydara.tse.exceptions، با کلاس پایهٔ PyDaraError
نشانی نسخه در PyPI (تأیید انتشار در AI_VERIFICATION.json): https://pypi.org/project/pydara/{version}/
نصب: python -m pip install pydara=={version}
امکانات فایل و Notebook: python -m pip install "pydara[files,notebook]=={version}"
حداقل Python اعلام‌شده: 3.12

۲. آنچه تا اینجا انجام شده
پروژهٔ اولیه با نام tse-dara و import قدیمی tse_dara عرضه می‌شد.
در نسخهٔ 0.6.0a1 نام توزیع pydara شد، ولی namespace هنوز یکسان نبود.
در نسخهٔ 0.6.0a2 نام توزیع، namespace، مثال‌ها، ابزارها و پوشهٔ کد یکدست شدند.
ساختار درست آینده pydara.tse است؛ هیچ compatibility import برای dara یا tse_dara عرضه نمی‌شود.
انتشار Wheel و بستهٔ منبع 0.6.0a2 و نصب مستقیم آن از PyPI در زمان تحویل آن نسخه بررسی شد.
برای نسخه‌های بعدی، نتیجهٔ تأییدشده را از AI_VERIFICATION.json بخوان.
نام اولیهٔ dara در PyPI با خطای مجوز رد شد؛ نام نهایی انتخاب کاربر pydara است.
حذف پروژهٔ قدیمی از PyPI در آخرین وضعیت ثبت‌شده تأیید نشده است؛ آن را انجام‌شده فرض نکن.

۳. نقشهٔ کد
src/pydara/__init__.py: نسخه و بارگذاری تنبل tse؛ import نباید شبکه یا پایگاه بسازد.
tse/__init__.py: رابط عمومی، تنظیمات کلاینت پیش‌فرض و توابع ساده.
tse/client.py و async_client.py: کلاینت همگام و ناهمگام؛ رفتارشان باید هم‌ارز باشد.
tse/engine.py و config.py: سیاست دریافت، تازگی، کش، مسیر ذخیره و پیکربندی.
tse/transport.py و providers/: HTTP، قرارداد درخواست و تبدیل پاسخ واقعی منبع.
tse/_core/: مدل‌ها و خطاهای داخلی TSE.
tse/instrument_lookup.py: شناسایی دقیق ابزار و سیاست چندنتیجه و تعارض.
tse/frames.py، pandas_tools.py و friendly.py: مدل جدول، schema، اعتبارسنجی و رابط Pandas.
tse/history.py، sync.py و history_models.py: تاریخچه، بازبینی و دریافت تکمیلی.
tse/market*.py و extended*.py: دیده‌بان، مشتریان، شاخص‌ها و داده‌های تکمیلی.
tse/workflows.py و workflow_client.py: عملیات گروهی، ادامه از checkpoint، catalog و backup.
tse/storage/: ذخیرهٔ پاسخ، تاریخچهٔ نسخه‌دار و codec امن فایل.
tse/io.py: CSV، Excel، Parquet و SQLite؛ CSV باید همراه sidecar منتقل شود.
tse/samples/: داده و transport مصنوعی برای آموزش و آزمون بدون اینترنت.
tse/api_catalog.json و reference.py: مرجع قابل خواندن از داخل کتابخانه.
tests/: قراردادهای اجرایی و رگرسیون‌ها؛ conftest جلوی شبکهٔ خارجی آزمون‌ها را می‌گیرد.
examples/: ۱۹ Notebook و نمونهٔ پایتون؛ نمونه‌های زنده صریح و اختیاری‌اند.
docs/: امضاهای API، طرح ذخیره و سوابق بررسی منابع سرویس.
tools/: ساخت، checksum، بررسی نصب، تولید مرجع، انتشار و ساخت همین بستهٔ تحویل.

۴. قابلیت‌های فعلی و حدود آنها
نماد و ابزار، قیمت و تاریخچهٔ روزانه، دیده‌بان، دادهٔ مشتریان، شاخص‌ها و تاریخچهٔ شاخص؛
معاملات و مظنه‌های گزارش‌شده، وضعیت و آستانه‌ها، مالکیت و تعداد سهام، رخدادهای تعدیل،
خروجی تعدیل‌شدهٔ سرویس منبع، NAV و صندوق، پیام‌ها و اختیارها.
درگاه جداگانهٔ آتی آزمایشی است. پوشش و دسترسی هر سرویس محدود به شواهد و قرارداد آن است.
فهرست دیده‌بان فعلی، فهرست کامل تاریخی ابزارها نیست. تعدیل منبع، تضمین بازده کل یا
دادهٔ نقطه‌درزمان نیست. زمان دریافت، الزاماً زمان انتشار رسمی داده نیست.
جدول معمولاً DataFrame و قیمت ساده Decimal است؛ نوع خروجی دقیق را از امضا و آزمون بخوان.
قابلیت‌های تحلیل، ML، بیتکوین، نرخ ارز و طلا و بازارهای کشورهای دیگر هنوز پیاده نشده‌اند.

۵. قراردادهای مهمی که باید حفظ شوند
on_multiple="all" پیش‌فرض است؛ first ترتیب منبع را حفظ می‌کند و error ابهام را رد می‌کند.
on_conflict="error" پیش‌فرض است؛ ins_code فقط با شناسهٔ صریح مجاز است.
FetchPolicy.fresh() درخواست تازه را تعیین می‌کند؛ online به‌تنهایی مانع استفاده از کش تازه نیست.
آفلاینِ دارای دادهٔ منقضی به اجازهٔ صریح allow_stale=True نیاز دارد.
رسید queued اثبات ذخیرهٔ پایدار نیست. خطای autosave نباید دادهٔ دریافت‌شده را از دست بدهد.
شناسه‌ها رشته‌اند؛ آنها را به float تبدیل نکن. قرارداد نوع ستون‌ها و زمان‌ها را حفظ کن.
آرشیوها ساختاری و نوع‌دار هستند؛ pickle یا اجرای کد از متادیتا وارد نکن.

۶. سازگاری ذخیره‌سازی
متادیتای تازه frame.attrs['pydara']، قالب تازه pydara-frame، sidecar تازه .pydara.json،
شیت متادیتای Excel تازه _pydara_meta و کلید Parquet تازه pydara هستند.
کش تازه در پوشهٔ دادهٔ pydara با فایل pydara.sqlite3 ساخته می‌شود.
خواندن نام‌های قبلی فایل، مسیر، شیت، کلید متادیتا و آرشیو پشتیبانی می‌شود.
نام‌های داخلی طرح SQLite حفظ شده‌اند تا پایگاه‌های قبلی قابل خواندن باشند.
برخورد با چنین نام‌هایی به معنی import یا وابستگی به بستهٔ قدیمی نیست.
تست‌های test_pydara_migration.py و test_pydara_namespace.py این مرزها را بررسی می‌کنند.

۷. وضعیت محیط کاربر (فقط برای ادامه روی همان رایانه)
پروژه: G:\\My progect\\Python\\TSE\\Lib\\pydara
محیط اصلی کاربر: G:\\My progect\\Python\\TSE\\venv\\python.exe
محیط ساخت جداگانه در .venv-publish بوده و عمداً داخل ZIP نیست.
در بررسی محیط اصلی با Python 3.14.8، بستهٔ tse-dara حذف و pydara[files,notebook]==0.6.0a2 نصب شد.
importهای قدیمی در بررسی فرآیند تازه پیدا نشدند؛ نمونهٔ sync/async و چهار قالب فایل موفق بودند.
۳۹ Notebook شامل checkpointها در codes کاربر مهاجرت و ۲۴۳ سلول کد بررسی شدند.
Notebookهای شخصی و خروجی‌های کاربر در این ZIP قرار ندارند؛ examples نمونه‌های کتابخانه‌اند.
دو تعارض جداگانهٔ موجود متعلق به pytse-client با black و lxml گزارش شد؛ آنها را بدون
نیاز مرتبط با درخواست، دستکاری یا به خطای pydara نسبت نده.
روی رایانه یا محیط دیگری این مسیرها را نساز؛ مسیر و interpreter واقعی آن محیط را تشخیص بده.

۸. اعتبارسنجی و انتشار بعدی
AI_VERIFICATION.json شواهد اجراشده را از کارهای اجرا‌نشده جدا می‌کند.
سابقهٔ نسخهٔ 0.6.0a2: آزمون کامل ثبت‌شده پیش از سه آزمون تازه، ۶۹۳ موفق روی Windows/Python 3.13.1 بود.
پس از آخرین تغییر، ۲۵ آزمون مرتبط با namespace، مهاجرت و بسته‌بندی موفق بودند؛
سه مورد تازهٔ خواندن container قدیمی نیز داخل همین ۲۵ مورد هستند.
موفقیت نمونهٔ Python 3.14.8 معادل اجرای همهٔ آزمون‌ها روی آن نسخه نیست.

روال معمول توسعه:
    python -m pip install -e ".[test,files]" build twine
    python tools/generate_api_reference.py
    python tools/build.py
    python -m pytest -q
    python tools/verify_installation.py
verify_installation را روی نصب Wheel و بدون سایه‌انداختن checkout/PYTHONPATH اجرا کن.
build.py ابتدا Wheel، سپس BUNDLE.json و در پایان source archive را می‌سازد.
برای انتشار، فقط فایل‌های نسخهٔ دقیق را به پوشهٔ .pypi-dist/<version> آماده کن،
SHA256SUMS.json را از همان فایل‌ها بساز و twine check --strict را اجرا کن.
tools/publish_pypi.ps1 از همین مسیر و checksumها استفاده می‌کند و فرض می‌کند
.venv-publish روی همان سیستم آماده است؛ آن محیط در این ZIP تحویل داده نمی‌شود.
توکن داخل ZIP نیست و نباید داخل کد، گزارش یا چت قرار بگیرد.
پس از انتشارِ درخواستی، فایل‌های PyPI، checksum و نصب از index را بررسی کن.
این فایل ZIP برای تحویل به AI است، نه جایگزین انتشار PyPI و نه محیط آفلاین کامل.

۹. استفاده از همین بسته
کد src و آزمون‌ها کامل‌اند؛ Wheel فعلی نیز برای کارکرد install.py و BUNDLE.json آمده است.
AI_PACKAGE_MANIFEST.json برای هر عضو، SHA256 و اندازه را ثبت می‌کند؛ خودش self-hash ندارد.
محیط‌ها، کش، پایگاه، credential، خروجی Notebook، نسخه‌های قبلی و backupهای شخصی حذف شده‌اند.
برای نسخهٔ بعدی این بسته را با python tools/create_ai_bundle.py بازسازی کن.
"""


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    if project["name"] != "pydara":
        raise ValueError("Unexpected distribution name")
    tree = ast.parse((ROOT / "src/pydara/__init__.py").read_text(encoding="utf-8"))
    code_version = next(
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    )
    if code_version != version:
        raise ValueError("Project and source versions differ")
    bundle = json.loads((ROOT / "BUNDLE.json").read_text(encoding="utf-8"))
    wheel = (ROOT / bundle["wheel"]).resolve()
    if not wheel.is_relative_to(ROOT) or not wheel.is_file() or bundle["package_version"] != version:
        raise ValueError("Build the current wheel and refresh BUNDLE.json first")
    if sha256(wheel.read_bytes()).hexdigest() != bundle["wheel_sha256"]:
        raise ValueError("Wheel checksum differs from BUNDLE.json")
    with ZipFile(wheel) as installed_archive:
        wheel_runtime = {name for name in installed_archive.namelist()
                         if name.startswith("pydara/") and not name.endswith("/")}
        source_runtime = {path.relative_to(ROOT / "src").as_posix()
                          for path in (ROOT / "src/pydara").rglob("*")
                          if path.is_file() and path.suffix in {".py", ".json", ".typed"}}
        if wheel_runtime != source_runtime or any(
            installed_archive.read(name) != (ROOT / "src" / name).read_bytes()
            for name in wheel_runtime
        ):
            raise ValueError("Current runtime source differs from the bundled wheel")

    entries: dict[str, bytes] = {}
    root_files = ["pyproject.toml", "MANIFEST.in", "README.md", "README_FA.md", "LICENSE",
                  "THIRD_PARTY_NOTICES.md", "SECURITY.md", "CHANGELOG.md", ".gitignore",
                  "BUNDLE.json", "install.py", "INSTALL_WINDOWS.bat"]
    paths = [ROOT / name for name in root_files]
    extensions = {".py", ".json", ".md", ".html", ".ipynb", ".ps1", ".yml", ".yaml"}
    for folder in ("src/pydara", "tests", "tools", "docs", "examples", ".github"):
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and (p.suffix in extensions or p.name == "py.typed")
                     and not any(part in {"__pycache__", ".ipynb_checkpoints"} for part in p.parts))
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("A selected file resolves outside the project")
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix == ".ipynb":
            notebook = json.loads(path.read_text(encoding="utf-8"))
            for cell in notebook["cells"]:
                if cell["cell_type"] == "code":
                    cell["outputs"] = []
                    cell["execution_count"] = None
            data = json.dumps(notebook, ensure_ascii=False, indent=1).encode("utf-8")
        else:
            data = path.read_bytes()
        if path.suffix == ".py":
            ast.parse(data.decode("utf-8"), filename=relative)
        entries[relative] = data
    entries[wheel.relative_to(ROOT).as_posix()] = wheel.read_bytes()
    entries["00_PROMPT_FA.txt"] = prompt(version).encode("utf-8")
    entries["01_PROJECT_GUIDE_FA.txt"] = guide(version).encode("utf-8")

    suite = ET.parse(ROOT / "reports" / f"pydara-{version}-tests.xml").getroot()
    status_path = ROOT / "reports/migration-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    status_matches = status.get("version") == version
    publication_verified = status_matches and status.get("publication_status") == "published"
    verification = {
        "snapshot_version": version,
        "distribution": "pydara", "namespace": "pydara", "public_module": "pydara.tse",
        "recorded_full_test_report": [
            {key: node.attrib[key] for key in ("tests", "errors", "failures", "skipped", "time")
             if key in node.attrib} for node in suite.iter("testsuite")
        ],
        "later_targeted_tests_passed": status.get("final_namespace_migration_packaging_tests_passed") if status_matches else None,
        "scope_note": "For 0.6.0a2, the full report precedes three added migration tests; the later targeted run covers them.",
        "published_version_install_verified": version if publication_verified and status.get("installation_from_pypi_verified") else None,
        "historical_runtime_verification_version": "0.6.0a2",
        "runtime_environments_checked": [
            {"python": "3.13.1", "os": "Windows", "checks": "full suite and final targeted tests"},
            {"python": "3.14.8", "os": "Windows", "checks": "installed package, sync/async samples, four file formats"},
        ],
        "user_environment_legacy_package_uninstalled": True,
        "user_notebooks_migrated": 39, "user_notebook_code_cells_checked": 243,
        "live_market_accuracy_certified": False,
        "old_pypi_project_deletion_confirmed": False,
        "exclusions": ["environments", "user databases", "caches", "credentials", "old releases", "personal notebooks", "notebook outputs"],
    }
    entries["AI_VERIFICATION.json"] = json.dumps(verification, indent=2).encode("utf-8")
    for name, data in entries.items():
        if name.endswith(".whl"):
            continue
        if re.search(rb"pypi-[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
            raise ValueError(f"Potential credential found in {name}")
    manifest = {
        "project": "pydara", "version": version, "manifest_excludes_own_digest": True,
        "files": {name: {"bytes": len(data), "sha256": sha256(data).hexdigest()}
                  for name, data in sorted(entries.items())},
    }
    entries["AI_PACKAGE_MANIFEST.json"] = json.dumps(manifest, indent=2).encode("utf-8")
    OUTPUT.mkdir(exist_ok=True)
    destination = OUTPUT / f"PyDara_{version}_AI_Handoff.zip"
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr("pydara/" + name, data)
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        for name, spec in manifest["files"].items():
            if sha256(archive.read("pydara/" + name)).hexdigest() != spec["sha256"]:
                raise ValueError(f"ZIP content mismatch: {name}")
    digest = sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(digest + "  " + destination.name + "\n", encoding="ascii")
    prompt_file = OUTPUT / f"Prompt_PyDara_{version}_FA.txt"
    prompt_file.write_text(prompt(version), encoding="utf-8")
    print(json.dumps({"zip": str(destination), "bytes": destination.stat().st_size,
                      "files": len(entries), "prompt": str(prompt_file), "sha256": digest}))


if __name__ == "__main__":
    main()
