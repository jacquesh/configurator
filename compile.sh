nuitka --standalone --python-flag=no_site --remove-output configurator.py
rm -r configurator/
mv configurator.dist/ configurator/
cp configurator.py README.md conf compile.sh configurator/
7z a -r -tzip configurator_$(date -Idate).zip ./configurator/
