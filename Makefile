REPOSITORY_ROOT := $(shell pwd)
BAZEL_ROOT      := $(REPOSITORY_ROOT)
BAZEL_NAMESPACE := org_fraggles
BAZEL_APP       := build_action_scheduler

bazel_clean:
	@cd $(BAZEL_ROOT) && bazel clean --expunge $(ARGS)

bazel_pip_requirements:
	@cd $(BAZEL_ROOT) && bazel run //tools:requirements.update && bazel run //:gazelle_python_manifest.update

bazel_gazelle:
	@cd $(BAZEL_ROOT) && bazel run //:gazelle -- $(ARGS)

bazel_buildifier:
	@cd $(BAZEL_ROOT) && bazel run @buildifier_prebuilt//:buildifier -- --lint=fix -r $(BAZEL_ROOT) $(ARGS)

bazel_isort:
	@cd $(BAZEL_ROOT) && bazel run //tools/isort:isort_bin -- --settings-path $(BAZEL_ROOT)/tools/isort/.isort.cfg $(BAZEL_ROOT)/$(BAZEL_NAMESPACE) $(ARGS)

bazel_black:
	@cd $(BAZEL_ROOT) && bazel run //tools/black:black_bin -- $(BAZEL_ROOT)/$(BAZEL_NAMESPACE) $(ARGS)

bazel_python_format_files: bazel_gazelle bazel_buildifier bazel_isort bazel_black

bazel_python_app_build:
	@cd $(BAZEL_ROOT) && bazel build --build_python_zip //$(BAZEL_NAMESPACE)/$(BAZEL_APP):$(BAZEL_APP)_bin -- $(ARGS)

bazel_python_test:
	@cd $(BAZEL_ROOT) && bazel test --test_output=all //$(BAZEL_NAMESPACE)/... -- $(ARGS)

bazel_python_build:
	@cd $(BAZEL_ROOT) && bazel build //$(BAZEL_NAMESPACE)/... -- $(ARGS)
