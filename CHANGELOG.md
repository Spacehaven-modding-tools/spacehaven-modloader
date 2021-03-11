# Change Log
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
