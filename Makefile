ifndef GBDK_HOME
	GBDK_HOME = ~/gbdk/
endif

PROJECTNAME = LabyrinthOfTheDragon

SRC_DIR = src
DATA_DIR = data
OBJ_DIR = obj
RES_DIR = res

ROM_BANKS=32
RAM_BANKS=4
CART_TYPE=0x1B

# The game's major and minor version. Every build adds the patch, the number of
# commits since this line last changed, and shows the result on the file screen:
# v1.1.4 from `make RELEASE=1`, and v1.1.4+ from any other build. Keep the
# changelog's latest heading and the credits card's fork line in step with it.
VERSION=1.1

# Cartridge header: the title (up to 11 characters) and the mask-ROM version
# byte at 0x14C, which carries the major version.
ROM_TITLE=LABYRINTH
ROM_VERSION=$(firstword $(subst ., ,$(VERSION)))

LCC = $(GBDK_HOME)bin/lcc
LCCFLAGS = -Wm-yC -Wm-yt$(CART_TYPE) -Wl-yo$(ROM_BANKS) -Wl-ya$(RAM_BANKS) \
	-Wm-yn"$(ROM_TITLE)" -Wm-yp0x14C=$(ROM_VERSION)

PNG2BIN := ./tools/png2bin
TABLES2C := ./tools/tables2c
STRINGS2C := ./tools/strings2c
VERSION2H := ./tools/version2h

# GBDK_DEBUG = ON
ifdef GBDK_DEBUG
	LCCFLAGS += -debug -v
endif

BIN = $(PROJECTNAME).gbc
SRC_FILES = $(wildcard $(SRC_DIR)/*.c)
DATA_FILES = $(wildcard $(DATA_DIR)/*.c)
OBJ_FILES = $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SRC_FILES)) \
	$(patsubst $(DATA_DIR)/%.c,$(OBJ_DIR)/%.o,$(DATA_FILES))
# Headers every object depends on, so that editing one rebuilds what includes
# it. Otherwise the linked ROM can mix objects compiled against different
# versions of a header, such as an enum whose values shifted. src/strings.h is
# rewritten by every `make assets`, so it is left out; depending on it would
# turn every build into a full rebuild.
HDR_FILES = $(filter-out $(SRC_DIR)/strings.h,$(wildcard $(SRC_DIR)/*.h))

MAP_FILES = $(wildcard $(RES_DIR)/maps/%.tilemap)
TILEMAP_FILES = $(wildcard $(RES_DIR)/tilemaps/%.tilemap)
TILEPNG := $(wildcard assets/tiles/*.png)
TILEBIN := $(subst assets/,res/,$(patsubst %.png,%.bin,$(TILEPNG)))

.PHONY: all clean usage assets data rom

# Two passes, on purpose. SRC_FILES and DATA_FILES above are wildcards, and make
# expands them while parsing, before any recipe runs. In a fresh clone, or after
# `make clean` has deleted the generated src/tables.c and data/strings_*.bank*.c,
# a single pass parses the Makefile with those files absent and links a ROM
# without its stat and string tables. Generating the assets in this pass and
# compiling in a sub-make means the wildcards are expanded after the generated
# sources exist.
all: assets
	@$(MAKE) --no-print-directory rom

rom: data $(BIN)

assets: asset_dirs strings tables version $(TILEBIN)

asset_dirs:
	mkdir -p res/tiles

tables: assets/tables.csv
	$(TABLES2C)

strings: assets/strings.js
	$(STRINGS2C)

version:
	$(VERSION2H) $(VERSION) $(if $(RELEASE),--release)

res/tiles/%.bin: assets/tiles/%.png
	$(PNG2BIN) $< $@

$(BIN): $(OBJ_FILES)
	$(LCC) $(LCCFLAGS) -o $@ $^

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c $(HDR_FILES) | $(OBJ_DIR)
	$(LCC) $(LCCFLAGS) -c $< -o $@

data:
	touch $(DATA_DIR)/*.c

$(OBJ_DIR)/%.o: $(DATA_DIR)/%.c $(HDR_FILES) | $(OBJ_DIR)
	$(LCC) $(LCCFLAGS) -c $< -o $@

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

usage:
	~/gbdk/bin/romusage $(BIN)

clean:
	rm -f *.o *.lst *.map *.gb *.gbc *.ihx *.sym *.cdb *.adb *.asm *.noi *.rst
	rm -f res/tiles/*.bin res/tiles/manifest.json
	rm -f res/color_tables/*.bin res/color_tables/manifest.json
	rm -f data/strings_*bank*.c
	rm -f obj/*
	rm -f src/strings.h
	rm -f src/tables.c
	rm -f src/version.h
