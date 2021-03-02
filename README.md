# Space Haven Mod Loader development Fork

This fork of the mod loader is for development with the intent of being pulled into the main project.

Do not download from here.
Instead, goto the [Tahvohck's modloader fork](https://github.com/Tahvohck/spacehaven-modloader).

New Features in this Fork:
- CHANGE version.py now prints version number.
- CHANGE annotation now opens the core folder instead of the library folder, because that's where the CSV are put.
- NEW ./tools/setup-windows.bat to install correct versions of dependencies.  Needs more testing.
- NEW ./tools/build-windows.bat to compile into PyInstaller EXE and compress into 7zip or zip file, depending on whether 7-Zip is installed.
- Implemented Tech and TechTree annotations.
- Implemented MainCat annotations.
- Implemented DataLogFragment annotions.
- Added "_linkedBy" attribute to Elements.
- Element, Product, Tech, and TechTree now exported to their own XML files.
- Export CSV files for Element, Item, Product, Tech, and TechTree.
