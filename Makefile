DIT_NAME=$(shell ddit targetname)

PKG_FILES=$(shell find pkg -type f)
SRC_FILES=$(shell find src -type f)

.PHONY: clean

all: ${DIT_NAME}

# This makefile depends on 'ddit' which can be installed
# with 'pip3 install daml-dit-ddit'

publish: ${DIT_NAME}
	ddit release

${DIT_NAME}: dabl-meta.yaml Makefile ${PKG_FILES} ${SRC_FILES} requirements.txt
	ddit build --force --integration

clean:
	rm -fr ${DIT_NAME} .daml dist *~ pkg/*~
