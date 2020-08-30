
doc : docs/index.html

docs/index.html : circuitgraph/* docs/templates/*
	pdoc --html circuitgraph --force --template-dir docs/templates
	cp -r html/circuitgraph/* docs

test :
	python -m unittest

coverage :
	coverage run -m unittest
	coverage html

dist : setup.py
	rm -rf dist/* build/* circuitgraph.egg-info
	python3 setup.py sdist bdist_wheel

upload : dist
	#python3 -m twine upload dist/*
	python3 -m twine upload --repository testpypi dist/*
