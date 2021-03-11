# Space Haven Mod Loader development Fork

This fork of the mod loader is for development with the intent of being pulled into the main project.
It was only tested against the Windows 10 Steam version of SpaveHaven 0.11.2

Do not download from here.
Instead, goto the [Tahvohck's modloader fork](https://github.com/Tahvohck/spacehaven-modloader).


New Features in this Fork:
- CHANGE version.py now prints version number.
- CHANGE annotated files are no longer placed in the game sub directory, but instead in the folder under `mods`.
- CHANGE annotation now opens the core mod folder instead of the library folder.
- NEW ./tools/setup-windows.bat to install correct versions of dependencies.  Needs more testing.
- NEW ./tools/build-windows.bat to compile into PyInstaller EXE and compress into 7zip or zip file, depending on whether 7-Zip is installed.
- Implemented Tech and TechTree annotations.
- Implemented MainCat annotations.
- Implemented DataLogFragment annotions.
- Added "_linkedBy" attribute to Elements.

KNOWN ERRORS:
- The new `build-windows.bat` doesn't get all proper dependencies.  I need someone's help with this.


TODO:
- Element, Product, Tech, TechTree, and maybe every section exported to their own XML files.
- Export CSV files for some or all sections.
- Reports.  Dependencies, relationships, foreign key lookups, etc.
- Export the modded XML to a folder under `mods` so that modders can see the result.


