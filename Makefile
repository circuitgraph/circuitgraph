
doc : docs/index.html

docs/index.html : circuitgraph/*
	pdoc --html circuitgraph --force --template-dir docs/templates
	cp html/circuitgraph/* docs

test :
	python -m unittest

coverage:
	coverage run -m unittest
	coverage html
