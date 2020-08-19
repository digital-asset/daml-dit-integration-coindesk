BASENAME=$(shell yq -r '.catalog.name' < dabl-meta.yaml)
VERSION=$(shell yq -r '.catalog.version' < dabl-meta.yaml)

TAG_NAME=${BASENAME}-v${VERSION}
NAME=${BASENAME}-${VERSION}
DAR_NAME=${BASENAME}.dar

.PHONY: clean install

all: ${NAME}.dit

publish: ${NAME}.dit
	git tag -f "${TAG_NAME}"
	ghr -replace "${TAG_NAME}" "${NAME}.dit"

${NAME}.dit: ${NAME}.pex dist/${DAR_NAME} dist Makefile
	cd dist; zip -r ../${NAME}.pex .
	mv ${NAME}.pex ${NAME}.dit

${NAME}.pex: $(find src -not -type d) requirements.txt
	 pex -o $@ \
		--disable-cache \
		-D src/ \
		-m daml_dit_api.main \
		-r requirements.txt \
		--inherit-path \
		--platform current \
		--platform manylinux2014_x86_64-cp-38-cp38

dist: $(find pkg) dabl-meta.yaml
	mkdir -p $@
	cp dabl-meta.yaml $@
	(cd pkg && tar czvf - .) | (cd dist && tar xzvf -)

dist/${DAR_NAME}: dist daml.yaml $(find daml -name *.daml)
	daml build -o dist/${DAR_NAME}

clean:
	rm -fr ${NAME}.dit ${NAME}.pex .daml dist *~ pkg/*~

install:
	cp ${NAME}.dit ../../daml-cloud/arcade-repo/arcade

run:
	PYTHONPATH=src python3 -m core_int.main
