
main:
	cd exercises; make
	./prepend.py
	cp -rf exercises/images exercises_assignment/.
	cp -rf exercises/images exercises_solution/.

book: main
	jb build .

pdf:
	jupyter-book build . --builder pdflatex

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
