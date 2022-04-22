
doc : docs/index.html

docs/index.html : circuitgraph/* docs/templates/*
	pdoc --html circuitgraph --force --template-dir docs/templates
	cp -r html/circuitgraph/* docs

test :
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	python3 -m unittest
	python3 -m doctest circuitgraph/*.py

test_% :
	python3 -m unittest tests/test_$*.py

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
