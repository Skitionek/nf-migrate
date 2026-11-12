from editops import find, first_of, load, migration_path, op, replace_ops

path = migration_path("4.0.3")
operations = load(path).operations
poster = ".github/workflows/pr-comment.yml"
create = find(operations, poster, kind="CreateFile")
template = operations[create].content
start = template.index("      - name: Read comment metadata\n")
end = template.index("      - name: Post PR comment\n")
old_step = template[start:end]
new_step = """\
      - name: Read comment metadata
        id: meta
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          RUN_HEAD_REPO: ${{ github.event.workflow_run.head_repository.full_name }}
          RUN_HEAD_BRANCH: ${{ github.event.workflow_run.head_branch }}
        run: |
          echo "::group::Downloaded pr-comment contents"
          ls -la pr-comment 2>/dev/null || echo "No pr-comment/ directory was downloaded."
          echo "::endgroup::"

          if [ ! -d pr-comment ]; then
            echo "No pr-comment artifact found; nothing to post."
            exit 0
          fi

          if [ ! -f pr-comment/comment.md ]; then
            echo "Artifact present but no comment.md; nothing to post."
            exit 0
          fi

          pr_number=$(cat pr-comment/pr_number.txt)
          header=$(cat pr-comment/header.txt)

          # The artifact comes from a workflow that the author of a fork PR
          # controls, so nothing in it is trusted. Check both values before
          # they are logged, used in an API path or written to $GITHUB_OUTPUT.
          case "$pr_number" in
            ''|*[!0-9]*)
              echo "Invalid PR number in pr_number.txt."
              exit 1
              ;;
          esac
          case "$header" in
            *[!A-Za-z0-9_-]*)
              echo "Invalid header in header.txt: only letters, digits, '-' and '_' are allowed."
              exit 1
              ;;
          esac
          echo "Found comment.md (header='$header', pr_number='$pr_number')."

          # The number must name the pull request this run was triggered for,
          # not just any pull request or issue: its head repository and branch
          # must be the run's. A run of a fork PR always has the fork and
          # branch it was opened from, so it cannot address a PR from any other
          # head. The pair stays the same when more commits are pushed after
          # the run started, so a run on an outdated head still posts.
          if [ -z "$RUN_HEAD_REPO" ] || [ -z "$RUN_HEAD_BRANCH" ]; then
            echo "The triggering run has no head repository or branch."
            exit 1
          fi
          if ! pr_head=$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '.head.repo.full_name + " " + .head.ref'); then
            echo "Could not look up pull request #${pr_number}."
            exit 1
          fi
          if [ "$pr_head" != "${RUN_HEAD_REPO} ${RUN_HEAD_BRANCH}" ]; then
            echo "Pull request #${pr_number} is not the pull request that triggered this run."
            exit 1
          fi

          echo "pr_number=$pr_number" >> "$GITHUB_OUTPUT"
          echo "header=$header" >> "$GITHUB_OUTPUT"
          echo "post=true" >> "$GITHUB_OUTPUT"
          echo "Will post comment to PR #${pr_number}."

"""
hardened = template[:start] + new_step + template[end:]
replace_ops(path, {
    create: first_of(poster, [
        op("CreateFile", poster, content=hardened),
        op(
            "Replace",
            poster,
            old=old_step,
            new=new_step,
            context_before="          if_no_artifact_found: ignore\n\n",
            context_after="      - name: Post PR comment\n"
            "        if: steps.meta.outputs.post == 'true'\n",
        ),
    ], "Hand-edited: the shared poster takes the PR number and the comment\n"
       "header from an artifact that a fork PR's own workflow writes, so it\n"
       "must not trust either. The metadata step checks that the number is a\n"
       "pull request with the head repository and branch of the run, and that\n"
       "the header is a plain slug. A pipeline that kept the template's\n"
       "poster gets just that step replaced."),
})
