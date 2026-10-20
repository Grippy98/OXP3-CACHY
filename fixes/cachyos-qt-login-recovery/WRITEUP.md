# Separating package failure from a black-panel report

The original incident followed a distribution upgrade: the panel remained detected but the graphical login process exited because Qt components imported a newer symbol version than the installed core supplied. The package version label alone was insufficient; a WebEngine package's library dependencies also needed inspection.

Recovery retained a compatible Qt/Plasma set from signed cached packages and then restarted the login manager. This is a dated recovery, not justification for applying those archived versions to a current installation. The durable fix belongs in distribution rebuilds and dependency metadata.

The installer therefore exposes instructions only. It does not downgrade packages, create permanent holds, switch repositories or use dependency-bypassing pacman flags.
