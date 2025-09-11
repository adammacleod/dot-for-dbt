# Feature Ideas

- Some kind of diff process. Either, build two versions of project into different schemas, and do some diff ontop. Or, the project is able to create copies of the models automatically and create diff models ontop. Maybe using dbt model versions? `dc diff dev dev@githash <model_name>` Creates a diff between a model in dev env at current dev and also at a specific hash. If that model is not built already @hash, then we should checkout the hash and build it. We could do some smart defers here to avoid rebuilding too much.

- What if we build our project into schemas which reference the git commit hash? `dc run dev@githash` would build a clean copy of `githash` into `schema_githash`. This could be accomplished by using `git worktree` which creates secondary working trees, independent from your repo.
  
  - For this, we can't override target_schema without updating schema inside of profiles.yml, we may need to create our own profiles.yml which creates extra configurations to target different schemas.

  - Additionally, we might need to use the --target-path arg of dbt to output manifests/output jsons into isolated folders per each "environment" we want to build into.

- Help with managing state and defer. ie: If we can build the project against empty commits, we can capture the manifest automatically, then always run state:modifed. We can also use defer to not have to rebuild anything from the base..

- Some capability to delete old schemas

- Support for red green deployments!! You can build the project into a temporary schema, and switch it over once you know it's built properly!

- Support for taking full control over schemas, IE: No objects in the schema which aren't meant to be in there from the project.

- Add a check when the CLI is run that the `.dot` directory is included in .gitignore. It is REALLY important that `.dot` isn't checked into git, so we should make it mandatory in .gitignore.

- Improve / test everything.

- Allow dot to fully manage your profiles dir. It could prompt on the command line for settings, automatically store them into env vars, or something along those lines. eg: store them safely!

- Make vscode fully ignore the .dot directory, this causes havoc when doing ctrl-p etc, although maybe it's useful to see what's in each worktree.

- A bit like dbt, dot specific config flags can be prefixed with `+` in the config files.

- Maybe add the ability to `+extend` within an environment, which lets you take all settings from another environment, but add any additional changes on top. Is this actually useful or just makes things harder? My use case is if you have two repos, maybe you want to sometimes build with the upstream as the CI for upstream, and sometimes you want to take upstream as your own private build of that repo.
