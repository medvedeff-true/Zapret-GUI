# medvedeff-winws

Windows x64 backend for the GUI's **Applications** mode only. The existing
`winws.exe` is still used for **All traffic** and **Lists**.

Build in a 64-bit Cygwin installation with `gcc-core`, `make`, `binutils`,
and `zlib-devel`: run `make cygwin64` here, then place the resulting
`medvedeff-winws.exe` in `resources/core/bin/medvedeff-winws`. Keep the
matching `cygwin1.dll`, `cygz.dll` and the bundled WinDivert files beside it.
See the notices and corresponding source references in that runtime folder.

`--app-scope-file` accepts a UTF-8 list with one absolute `.exe` path per line.
The GUI sends the file content to its existing background service. The service
launches its own installed copy of the engine and waits for the capture-ready
line. `--version` and `--dry-run` do not open the driver or require elevation.

TCP connections missing from the tracker, or reported under conflicting PIDs,
are checked against the Windows TCP owner table using the full connection tuple.
A cached miss is refreshed so a new connection's first data packet is not
skipped. Traffic without a confirmed selected owner is not sent to the desync
pipeline. An already-open UDP/QUIC connection may need to reconnect after
enabling bypass because the UDP owner table does not identify the remote endpoint.

Driver-free scope regression, from the repository root in Cygwin (with the
bundled `WinDivert.dll` beside the test executable or on `PATH`):

```sh
mkdir -p build
gcc -std=gnu99 -Itools/medvedeff-winws/windows \
    tests/medvedeff_winws_scope_test.c -Ltools/medvedeff-winws/windows/windivert \
    -lwindivert64 -o build/scope-test.exe
./build/scope-test.exe
```
