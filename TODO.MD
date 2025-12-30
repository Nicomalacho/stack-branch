1. gs commit is not working, it is throwing this error: Error, the program tried to call itself with '-m' argument. Disable with '--no-deployment-flag=self-execution'.
2. gs push, is not creating the pr
3. gs submit submits the branches but it is not creating the PRs
4. it is not adding the description, maybe we need logs when doing the push/submit and the comment
5. the diagram is failing:
Unable to render rich display

Parse error on line 3:
...es/pull/1'>branch-1 [#1]</a>] main -
-----------------------^
Expecting 'SQE', 'DOUBLECIRCLEEND', 'PE', '-)', 'STADIUMEND', 'SUBROUTINEEND', 'PIPE', 'CYLINDEREND', 'DIAMOND_STOP', 'TAGEND', 'TRAPEND', 'INVTRAPEND', 'UNICODE_TEXT', 'TEXT', 'TAGSTART', got 'SQS'
For more information, see https://docs.github.com/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams#creating-mermaid-diagrams

6. when doing changes in PR A the submit didn't update the PR B that it's based from PR A
7. when resolving the clonficts it should submit the changes to all the PRs that are in the stack from bottom to top
8. when doing a sync it should squash all commits into one single commit and then do the rebase from the parent PR that way we only need to solve conflics of one single commit