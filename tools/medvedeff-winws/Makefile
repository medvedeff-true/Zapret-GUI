CC = gcc
WINDRES = windres
CPPFLAGS += -Iwindows
CFLAGS += -std=gnu99 -Os -Wno-address-of-packed-member
LDFLAGS += -Wl,--gc-sections
LDLIBS += -lz -Lwindows/windivert -lwindivert64 -lwlanapi -lole32 -loleaut32
SOURCES = $(wildcard *.c crypto/*.c)
HEADERS = $(wildcard *.h crypto/*.h windows/windivert/*.h)
ICON = windows/res/64/winicon.o

.PHONY: all cygwin64 clean
all cygwin64: medvedeff-winws.exe

medvedeff-winws.exe: $(SOURCES) $(HEADERS) manifest.o $(ICON) windows/windivert/libwindivert64.a
	$(CC) $(CPPFLAGS) $(CFLAGS) -s -o $@ $(SOURCES) manifest.o $(ICON) $(LDFLAGS) $(LDLIBS)

manifest.o: windows/medvedeff-winws.rc windows/medvedeff-winws.manifest
	$(WINDRES) -Iwindows -i $< -o $@

clean:
	rm -f medvedeff-winws.exe manifest.o
