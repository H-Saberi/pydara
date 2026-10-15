# Third-party attribution

## Calendar arithmetic

The `_nowruz` routine in `src/pydara/tse/dates.py` adapts the
`jalCalCore` calendar-cycle calculation from **jalaali-js**, based on the
Borkowski Persian-calendar algorithm. Python date arithmetic and validation
around it are implemented for PyDara. Supported Jalali dates are intentionally
restricted to years 1200..1599, not the full upstream interval.

Source inspected 2026-10-13:
https://github.com/jalaali/jalaali-js/blob/master/src/index.ts
Git blob SHA: 14309485f93dd8eff2e30d7ba20ba38115457a74
License source: https://raw.githubusercontent.com/jalaali/jalaali-js/master/LICENSE

MIT License

Copyright (c) 2020 Behrang Norouzinia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## TSETMC access

TSETMC and its data are not owned by this project. This package does not
include market data; bundled sample responses are explicitly synthetic.
The MIT code license does not grant market-data redistribution permissions.
API paths/schema were reviewed using 5j9/tsetmc's source; its GPL code is not
bundled or made a runtime dependency. No authenticated API is guessed.
