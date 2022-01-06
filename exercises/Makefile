SRC := $(wildcard *master.ipynb)
ASSIGNMENTS := $(subst master,assignment,$(SRC))
SOLUTIONS := $(subst master,solution,$(SRC))

build: ${ASSIGNMENTS}

test:
	python -m unittest discover

%assignment.ipynb: %master.ipynb
	./sep.py $<
	nbstripout $@

clean:
	rm *-solution.ipynb
	rm *-assignment.ipynb
