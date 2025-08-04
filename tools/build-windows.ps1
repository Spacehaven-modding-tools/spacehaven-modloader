param(
	[switch]$Quiet,
	[switch]$NoOpenFolder,
	[switch]$SkipZip
)

$gitDir = git rev-parse --show-toplevel
$distPath = "dist/spacehaven-modloader"
$specfile = "modloader.spec"

function log {
	param(
		[Parameter(Position=0)]
		$WriteThis,
		[Parameter(Position=1)]
		[switch]$Quiet
	)
	if ($Quiet) { return }
	Write-Host -Fore Cyan $WriteThis
}

if ($null -eq $gitDir) {
	return 1
}
log "Jumping to root directory of repository" -Quiet:$Quiet
Push-Location $gitDir

if (Test-Path $distPath) {
	log "Removing automatic distribution directory (non-versioned)" -Quiet:$Quiet
	Remove-Item -r -force $distPath
}

log "Activated virtualenv and building based on ($specfile)"-Quiet:$Quiet
. env/Scripts/activate
$VERSION = python -c 'import version; print(version.version)'
$distPathVersioned = "$distPath-$VERSION.windows"

log "Build version $VERSION" -Quiet:$Quiet
python -m PyInstaller $specfile --clean
deactivate

if (Test-Path $distPathVersioned) {
	log "Removing old build of $VERSION" -Quiet:$Quiet
	Remove-Item -r -force $distPathVersioned
}

Move-Item  $distPath $distPathVersioned
$7z = Get-Command "7z"
if ($7z -and -not $SkipZip) {
	if (Test-Path "$distPathVersioned.zip") {
		log "Removing old zip file" -Quiet:$Quiet
		Remove-Item "$distPathVersioned.zip"
	}
	log "Found 7Zip, packing build" -Quiet:$Quiet
	. $7z a -spe -- ".\$distPathVersioned.zip" ".\$distPathVersioned"
}

Pop-Location
