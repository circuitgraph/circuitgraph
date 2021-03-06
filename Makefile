
doc : docs/index.html

docs/index.html : circuitgraph/* docs/templates/*
	pdoc --html circuitgraph --force --template-dir docs/templates
	cp -r html/circuitgraph/* docs

test :
	python3 -m unittest

test_% :
	python3 -m unittest circuitgraph/tests/test_$*.py

coverage :
	coverage run -m unittest
	coverage html

dist : setup.py
	rm -rf dist/* build/* circuitgraph.egg-info
	python3 setup.py sdist bdist_wheel

test_upload: dist
	python3 -m twine upload --repository testpypi dist/*

upload : dist
	python3 -m twine upload dist/*

install:
	pip3 install .

install_editable :
	pip3 install -e .
