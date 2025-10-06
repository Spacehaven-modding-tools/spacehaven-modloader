# Change Log
## v0.12.1
- Fix build missing annotate code

## v0.12.0
### New Modifiable Stuff
- Added modding of library/audio
### Engine
- Improved patch operations log and validations
- Added new patch operations
### Source Code Improvements
- Deleted some deprecated mod examples: the mod in Nexus serve as a better demo!
- Cleanup of unused python modules in source code => smaller requirements.txt
- Upgraded python to version 3.11.9
- Fixed zipfile error ("zip bomb") when upgrading python
- Fixed all lxml warnings
- Fixed build/dist scripts
- Fixed launch VSCode options
- Added python black and flake8 for the sake of clean development
- Fixes and coding style changes due to python black and flake8
- Removed lines of code spacehaven-modloader.py (toggle/var declarations), show in the IDE as errors
- Improved .gitignore file

## v0.10.0
### GitHub Issues Resolved
- #4 Add mod configuration options
- #5 Possible issue during CIM generation
- #7 Patch operation Add doesn't adhere to the PatchOperationAdd standard
- #19 Mod loader issue
### UI Changes
- List Box now has a scroll bar.
- Description frame now has a scroll bar.
- List Box and Description now can be resized.
- Small window sizes are handled better.
- Default window size increased.
### New Modifiable Sections
- Explosion
- FloorExpPackage
- GameScenario
- Robot
- RoofExpPackage
- Tech
- TechTree
### Mod Config Variables
- Modders can create variables that are user configurable.
- Variable values are saved at time of launch.
- Variables can be reset to defaults.
- Example mods included: "Electric Slide", "Engine Tuner", and "Robot Work".
- Known Issues - Variables do NOT have UI validation.
- Known Issues - All variables are a simple search-replace.
### Improved Annotations
- "Element" entries now have a "_linkedBy" that lists what Elements link to them.
- "Element" entries that produce or consume a resource now annotate that resource with its name.
- "Product" entries now have annotations for their needs and output.
- "DataLogFragment" now have an annotation with the file path.
- "GameScenario" now have name annotation.
- "SubCat" now have annotations.
- "PersonalitySettings/attributes/l" now annotated.
- "DifficultySettings" now have annotation for all resources and items.
- "Faction" entries now annotated.
- "Craft" now have name annotation.
- "DataLog" now have name annotation.
- "BackStory" now have name annotation.
- "TradingValues" entries now annotated with resource name.
- "CharacterTrait" now have name annotation.
- "CharacterCondition" now have name annotation.
- "MainCat" now have annotations.
- "TechTree" entries now have items annotation.
- "Robot" cost and repair elements are annotated with element name.
- And some others.
### Other
- Use of Python pip module "steamfiles" was removed.

## v0.9.1
- BUGFIX: AttributeAdd patch operations were universally failing due to missing variable.

## v0.9.0
- On Windows, the game will be autolocated via Steam if possible.
- `<modid>` tag in info.xml: Defines a prefix that can be used in various places during mod creation.
- Automatic texture packing: instead of defining a `textures` file, texture regions can be defined as needed in `animations`. Add a `filename=""` attribute to the `<assetPos />` tag, and it will be packed automatically into `modid.cim`. This will fail if a mod ID is not specified. Textures must still be located in `moddir/textures` and paths are relative to this directory.
- Automatic texture patching writes the resulting textures XML to `moddir/library/generated_textures.xml` for debugging
- Attempt to normalize file paths in a bunch of places
- More instances of log cleanup - less errors, more error messages
- Decouple mod database from window class
- Decouple mod info from window class

## v0.8.2
Bugfix: textures were not being merged in due to missing file during the build process

## v0.8.1
- New PatchOperation: AttributeMath (not in PatchOperation specification)
  - Requires an addtional attribute on the `<value />` tag: opType
  - Supported operations: `add`, `subtract`, `multiply`, `divide`
- `<Noload />` tag - Prevents a patch from loading (good for optional patches, or patches in development)
- Version bump to 0.8.1 to allow for better versioning in the future.
- General code refactoring

## v0.0.8
Support for [PatchOperation][1] modding
- AttributeSet -> PatchOperationAttributeSet
- AttributeAdd -> PatchOperationAttributeAdd
- AttributeRemove -> PatchOperationAttributeRemove
- Add -> PatchOperationAdd
- Insert -> PatchOperationInsert
- Remove -> PatchOperationRemove
- Replace -> PatchOperationReplace

Patches are loaded from `moddir/patches`, and are loaded after merge-by-id to allow modding other mods and to prevent clobbering.
Patch failure is logged to logs.txt

## v0.0.2
- Adds support for patching all definitions in `library/haven`, not just `Elements` and `Products`.
- Fixed a typo in launch button ("Spacehaven" -> "Space Haven")
- Adds logging to `mods/logs.txt` so you can see what it's doing (and report bugs)
- Adds game version checking/warnings

## v0.0.1
Initial Release


[1]: <https://rimworldwiki.com/wiki/Modding_Tutorials/PatchOperations>
