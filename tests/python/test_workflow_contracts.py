from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]


class WorkflowContractTests(unittest.TestCase):
    def test_publication_workflows_execute_only_trusted_code(self):
        for name in ("publish.yml", "emergency-withdraw.yml"):
            workflow = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertIn('cp -a src schemas requirements.lock "$TRUSTED_ROOT/"', workflow)
            self.assertIn('PYTHONPATH=%s/src', workflow)
            self.assertIn('git checkout --detach', workflow)
            self.assertNotIn('\n    env:\n      PUBLICATION_AUTHORIZATION_KEY: ${{ secrets.PUBLICATION_AUTHORIZATION_KEY }}', workflow)
            self.assertIn('env:\n          PUBLICATION_AUTHORIZATION_KEY: ${{ secrets.PUBLICATION_AUTHORIZATION_KEY }}', workflow)
            self.assertIn('persist-credentials: false', workflow)
            self.assertIn('--database "$RUNNER_TEMP/staged/$DATABASE_RECEIPT_PATH"', workflow)
            self.assertIn('--staged-file "$path=$RUNNER_TEMP/staged/$path"', workflow)
            self.assertNotIn('ACCOUNT_WIDE_SPEND_USD', workflow)
            self.assertNotIn('account_wide_spend_usd', workflow)

    def test_publication_context_is_protected_and_readback_is_pinned(self):
        for name in ("publish.yml", "emergency-withdraw.yml"):
            workflow = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertIn('PUBLICATION_OUTPUT_DIR: ${{ vars.PUBLICATION_OUTPUT_DIR }}', workflow)
            self.assertIn('PUBLICATION_TARGET_REF: ${{ vars.PUBLICATION_TARGET_REF }}', workflow)
            self.assertIn('PUBLICATION_READBACK_ORIGIN: ${{ vars.PUBLICATION_READBACK_ORIGIN }}', workflow)
            self.assertNotIn('output_dir:', workflow)
            self.assertNotIn('urlopen', workflow)
            self.assertIn('socket.getaddrinfo(host, 443', workflow)
            self.assertIn('ipaddress.ip_address(address[0]).is_global', workflow)
            self.assertIn('server_hostname=host', workflow)
            self.assertIn('if response.status != 200:', workflow)
            self.assertIn('WORKFLOW_REF: ${{ github.workflow_ref }}', workflow)
            self.assertIn('--workflow-ref "$WORKFLOW_REF"', workflow)
            self.assertNotIn('--workflow-ref "${{ github.workflow_ref }}"', workflow)

    def test_pages_candidate_code_never_has_deploy_authority(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
        self.assertIn("permissions:\n  contents: read\n", workflow)
        self.assertNotIn("permissions:\n  contents: read\n  pages: write\n  id-token: write", workflow)
        self.assertIn("build:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n      pages: read", workflow)
        build_permissions = workflow.split("  build:", 1)[1].split("  human-gate:", 1)[0]
        self.assertNotIn("pages: write", build_permissions)
        self.assertNotIn("id-token: write", build_permissions)
        self.assertIn("human-gate:\n    needs: build\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read", workflow)
        self.assertIn("deploy:\n    needs: [build, human-gate]\n    runs-on: ubuntu-latest\n    permissions:\n      pages: write\n      id-token: write", workflow)
        self.assertIn("SOURCE_REF: ${{ inputs.source_ref || github.sha }}", workflow)
        self.assertIn("[0-9a-f][0-9a-f][0-9a-f][0-9a-f]", workflow)
        self.assertIn("ref: ${{ steps.source.outputs.ref }}", workflow)
        self.assertNotIn("ref: ${{ inputs.source_ref || github.sha }}", workflow)
        self.assertIn("owner_deploy_override:", workflow)
        self.assertIn("owner_deploy_reason:", workflow)
        self.assertIn("eventName !== 'workflow_dispatch'", workflow)
        self.assertIn("actor.toLowerCase() !== repositoryOwner.toLowerCase()", workflow)
        self.assertIn("ownerReason.length < 20", workflow)
        self.assertIn("approved(approvals.usability, 'Usability approval')", workflow)
        self.assertIn("approved(approvals.design, 'Design approval')", workflow)
        self.assertIn("approved(approvals.browser, 'Browser-matrix approval')", workflow)
        self.assertNotIn("@v", workflow)
        for action in ("actions/checkout", "actions/setup-node", "actions/configure-pages", "actions/upload-pages-artifact", "actions/deploy-pages"):
            self.assertRegex(workflow, rf"uses: {re.escape(action)}@[0-9a-f]{{40}}")

    def test_mutation_coordinator_uses_workflow_sha(self):
        workflow = (ROOT / ".github" / "workflows" / "mutation.yml").read_text()
        self.assertIn("ref: ${{ github.workflow_sha }}", workflow)
        self.assertNotIn("ref: refs/heads/main", workflow)

    def test_publication_readback_origin_matches_repository_pages(self):
        for name in ("publish.yml", "emergency-withdraw.yml"):
            workflow = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertIn('owner, repo = os.environ["GITHUB_REPOSITORY"].lower().split("/", 1)', workflow)
            self.assertIn('expected_host = owner + ".github.io"', workflow)
            self.assertIn('expected_path = "" if repo == expected_host else "/" + repo', workflow)
            self.assertIn('origin.hostname.lower() != expected_host or origin.path.rstrip("/") != expected_path', workflow)

    def test_emergency_workflow_accepts_only_emergency_authorization(self):
        workflow = (ROOT / ".github" / "workflows" / "emergency-withdraw.yml").read_text()
        self.assertIn('authorization = json.load(open(os.environ["RUNNER_TEMP"] + "/authorization.json", encoding="utf-8"))', workflow)
        self.assertIn('authorization.get("operation") != "emergency"', workflow)
        self.assertNotIn("removal_only", workflow)
        self.assertNotIn("_require_removal_only", workflow)

    def test_audit_uses_signed_current_budget_evidence(self):
        workflow = (ROOT / ".github" / "workflows" / "audit.yml").read_text()
        self.assertNotIn('account_wide_spend_usd', workflow)
        self.assertNotIn('ACCOUNT_WIDE_SPEND_USD', workflow)
        self.assertIn('BUDGET_EVIDENCE_KEY: ${{ secrets.BUDGET_EVIDENCE_KEY }}', workflow)
        self.assertIn('--billing-evidence-key "$BUDGET_EVIDENCE_KEY"', workflow)
        self.assertIn('--verify-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"', workflow)
        self.assertIn('persist-credentials: false', workflow)

    def test_weekly_discovery_is_review_gated_and_does_not_publish(self):
        workflow = (ROOT / ".github" / "workflows" / "weekly-discovery.yml").read_text()
        self.assertIn('- cron: "0 0 * * 1"', workflow)
        self.assertIn("contents: write\n  pull-requests: write", workflow)
        self.assertIn('startswith("automation/discovery-")', workflow)
        self.assertIn("git show FETCH_HEAD:data/discovery/seen.v1.json", workflow)
        self.assertIn("git restore data/discovery/seen.v1.json data/discovery/candidates.v1.json", workflow)
        self.assertIn('git checkout -B "$EXISTING_BRANCH" "origin/$EXISTING_BRANCH"', workflow)
        self.assertIn("data/discovery/seen.v1.json data/discovery/candidates.v1.json", workflow)
        self.assertNotIn("git add data/site.v3.json", workflow)
        self.assertNotIn("git push --force", workflow)
        self.assertNotIn("this run made no changes", workflow)
        for action in ("actions/checkout", "actions/setup-python"):
            self.assertRegex(workflow, rf"uses: {re.escape(action)}@[0-9a-f]{{40}}")


if __name__ == "__main__":
    unittest.main()
