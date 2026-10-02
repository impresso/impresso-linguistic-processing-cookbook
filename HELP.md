# Make Help Conventions

This repository treats Make help as a small, composable command-line interface.
The root Makefile sets `help` as the default goal, so running `make` presents a
short index instead of starting work.

## Design Principles

- Keep `make help` short, stable, and safe to run without configuration.
- Group detailed commands by workflow: orchestration, processing, sync, setup,
  paths, sampling, aggregation, cleanup, and debugging.
- Let included Makefile fragments contribute help for the workflow they own.
- Show the current value of significant settings only in the detailed topic
  where that setting is relevant.
- Keep help recipes read-only: they explain targets and report configuration;
  they do not create files, sync data, or invoke external services.

## Public Interface

The shared [cookbook/help.mk](cookbook/help.mk) file declares the help targets
as phony and owns the top-level index. The root [Makefile](Makefile) includes
it before component fragments and sets:

```make
.DEFAULT_GOAL := help
```

Users discover a workflow through the index, then request its details:

```sh
make
make help
make help-processing
make help-sync
make help-setup
```

Topic names are verbs or workflow domains, not individual target names. This
keeps the index compact as a cookbook gains more components.

## Composable Topic Help

Use a double-colon rule (`::`) when a target is intentionally extended from
multiple fragments. Each included fragment can add lines to the same topic
without depending on a central registry or on another component being present.

```make
.PHONY: help-processing

help-processing::
	@echo "MY COMPONENT:"
	@echo "  my-component-target # Process the component input"
	@echo ""
	@echo "MY COMPONENT VARIABLES:"
	@echo "  MY_COMPONENT_OPTION=$(MY_COMPONENT_OPTION)"
```

The include order determines the order in which each `help-<topic>::` recipe
is printed. Put generic shared help first and component-specific blocks later.
For a target with one owner, a normal single-colon target is appropriate; do
not use it for a topic that other fragments must extend.

## Output Style

Use plain `echo` lines so help works with GNU Make and remains easy to scan:

```make
@echo "  target-name      # Brief imperative description"
@echo "                    # Optional continuation or caveat"
```

Conventions:

- Indent commands by two spaces and align the `#` descriptions within a group.
- Use uppercase section headings ending in `:`.
- Separate logical sections with one blank `@echo ""` line.
- Describe behavior, prerequisites, and caveats that affect a user's choice of
  target. Avoid repeating implementation details.
- Print effective variable values as `NAME=$(NAME)` in detailed help, especially
  for resource limits, validation flags, and processing mode switches.

## Target Metadata Comments

Human-readable topic help complements, rather than replaces, target metadata.
Document a target immediately above its rule using this form:

```make
# TARGET: my-component-target
#: Process the component input
my-component-target: prerequisites
```

For an extendable rule, identify the rule type explicitly:

```make
# DOUBLE-COLON-TARGET: processing-target
#: Contribute this component to generic processing
processing-target:: my-component-target
```

The `#:` one-line summary is significant: it is the concise description
reported by Make documentation tooling such as `remake --tasks`. Use the
longer surrounding comments for prerequisites, side effects, and rationale.
The repository's [cookbook/comment_template.mk](cookbook/comment_template.mk)
is the source template for these annotations.

## Recommended Layout for Another Cookbook

1. Add a shared `help.mk` early in the root Makefile's includes.
2. Mark `help` as the default goal in the root Makefile.
3. Make `help` print only a usage line and the available `help-<topic>` targets.
4. Declare all public help targets `.PHONY` in the shared file.
5. Have each setup, sync, processing, sampling, aggregation, and cleanup
   fragment append its commands to the topic it owns with `help-<topic>::`.
6. Add `TARGET` or `DOUBLE-COLON-TARGET` metadata directly above every public
   target rule.
7. Keep the README focused on common end-to-end commands and refer users to
   `make help` for the complete navigable interface.

## Verification

Run these checks after changing Make help:

```sh
make help
make help-processing
make help-sync
make help-setup
```

Check that the root index contains every supported topic, component fragments
appear in their expected topic, output order follows Makefile include order,
and no help target requires credentials, downloads dependencies, or mutates
local or remote state.
