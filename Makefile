
main:
	cd exercises; make
	./prepend.py
	cp -rf exercises/images exercises_assignment/.
	cp -rf exercises/images exercises_solution/.
	cd challenges; make
	cp challenges/*assignment.ipynb challenges_assignment/.
	cp challenges/boat_utils.py challenges_assignment/.
	cp -fr challenges/data challenges_assignment/.
	cp -rf challenges/images challenges_assignment/.

book: main
	jb build .

pdf: main
	jupyter-book build . --builder pdflatex

test:
	cd exercises; make test

open:
	open _build/html/index.html

links:
	# Bibtex database
	cp -rf ~/Git/zachs_macros/pubs.bib bibtex_database.bib

clean:
	jb clean .
	cd exercises; make clean
	cd exercises_assignment; make clean
	cd exercises_solution; make clean
	cd challenges; make clean
	cd challenges_assignment; make clean
