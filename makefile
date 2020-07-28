
doc : circuitgraph/*
	pdoc --html circuitgraph --force --template-dir docs/templates
	cp html/circuitgraph/* docs
