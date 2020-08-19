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

${NAME}.dit: dist/${DAR_NAME} dist Makefile
	cd dist; zip -r ../${NAME}.dit .

dist: $(find pkg) dabl-meta.yaml
	mkdir -p $@
	cp dabl-meta.yaml $@
	(cd pkg && tar czvf - .) | (cd dist && tar xzvf -)

dist/${DAR_NAME}: dist daml.yaml $(find daml -name *.daml)
	daml build -o dist/${DAR_NAME}

install:
	cp ${NAME}.dit ../../daml-cloud/arcade-repo/arcade

clean:
	rm -fr ${NAME}.dit .daml dist *~ pkg/*~
