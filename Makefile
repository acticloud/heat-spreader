clean:
	find . -name "__pycache__" | xargs rm -rf
	find . -name "*.pyc" | xargs rm -rf
	find . -name "*.egg-info" | xargs rm -rf
	rm -rf ./.tox
	rm -rf ./.pytest_cache
	rm -rf ./.eggs
	rm -rf ./pip-wheel-metadata
	rm -rf ./dist
	rm -rf ./build
	rm ./src/heatspreader/version.py

.PHONY: clean

wheel:
	python setup.py bdist_wheel

.PHONY: wheel
