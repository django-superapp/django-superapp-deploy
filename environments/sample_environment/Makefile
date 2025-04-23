
export CONFIG_YAML_PATH=$(realpath ./secrets/config_env.yaml)
export SCRIPT_DIR=$(realpath ../../)


setup-sealed-secrets:
	set -e; \
	$(SCRIPT_DIR)/scripts/setup-sealed-secrets.sh;


generate-skaffolds:
	@echo "Generating configs"; \
    set -e; \
	$(SCRIPT_DIR)/scripts/generate-skaffolds.sh;

generate-manifests:
	set -e; \
	$(SCRIPT_DIR)/scripts/generate-manifests.sh;

build-all-docker-images:
	set -e; \
	$(SCRIPT_DIR)/scripts/build-all-docker-images.sh;


# Skaffold commands
# This command must be executed with sudo
force-connect-telepresence:
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh && \
	(telepresence quit --stop-daemons || true) && \
	make connect-telepresence

connect-telepresence:
	# before running this script, setup telepresence by running:
	# make setup-telepresence
	# Make sure to run this script as rootSection
	# sudo make connect-telepresence
	# If this command fails, please run make force-connect-telepresence
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh && \
	telepresence quit -s && \
	telepresence connect

disconnect-telepresence:
	# before running this script, setup telepresence by running:
	# make setup-telepresence
	# Make sure to run this script as rootSection
	# sudo make connect-telepresence
	# If this command fails, please run make force-connect-telepresence
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh && \
	telepresence quit --stop-daemons

# copy-required-external-deps
build-and-push-images: common
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh && \
	find $$GENERATED_SKAFFOLD_DIR -mindepth 1  -maxdepth 1 -type d -exec basename \{} \; | parallel --tag --jobs 5 --halt soon,fail=1 'make build-skaffold-by-name name={}'

generate-ci-build-paths:
	set -e; \
	$(SCRIPT_DIR)/scripts/generate-ci-build-paths.sh;

build-skaffold-by-name:
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh; \
	echo "$$REGISTRY_PASSWORD" > docker login -u $$REGISTRY_USERNAME --password-stdin  $$REGISTRY_URL && \
	ulimit -n 65536; \
	echo "Building skaffold $$name with image tag $$IMAGES_TAG"; \
    skaffold build \
        --verbosity debug \
        --filename="$$GENERATED_SKAFFOLD_DIR/$$name/skaffold.yaml";

until-succeed:
	@echo "Executing \"${command}\" until-succeed";
	retries_i=0; \
	while ! ${command}; \
	do \
	        retries_i=$$((retries_i + 1)); \
	        if [ $$retries -eq $$retries_i ]; then \
	                echo "Max retries reached while executing \"${command}\". Exiting."; \
	                exit 1; \
	        fi; \
	        sleep $$retries_i; \
	done

# Deploy commands
deploy-using-skaffold:
	set -e; \
	$(SCRIPT_DIR)/scripts/deploy-using-skaffold.sh;

deploy-manifests-using-kubectl:
	set -e; \
	$(SCRIPT_DIR)/scripts/deploy-manifests-using-kubectl.sh;

deploy-using-fleet-manifests:
	set -e; \
	$(SCRIPT_DIR)/scripts/deploy-using-fleet-manifests.sh;

# Setup dev environment
setup-telepresence:
	set -e; \
	source $(SCRIPT_DIR)/scripts/common-env.sh && \
    telepresence helm install --set client.dns.includeSuffixes=svc --set client.routing.allowConflictingSubnets="{10.5.0.0/16}" || true && \
    telepresence helm upgrade

generate-sample-postgresql-certificates:
	set -e; \
	$(SCRIPT_DIR)/scripts/generate-sample-postgresql-certs.sh;