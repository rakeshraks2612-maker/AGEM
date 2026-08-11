.PHONY: install run

install:
	pip install -r requirements.txt

run:
	python -m agem.profiler
