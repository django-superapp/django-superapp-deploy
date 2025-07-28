from ilio import write

from ..base.constants import *


def json2xml(json_obj, line_padding=""):
    result_list = list()

    json_obj_type = type(json_obj)

    if json_obj_type is list:
        for sub_elem in json_obj:
            result_list.append(json2xml(sub_elem, line_padding))

        return "\n".join(result_list)

    if json_obj_type is dict:
        for tag_name in json_obj:
            sub_obj = json_obj[tag_name]
            result_list.append("%s<%s>" % (line_padding, tag_name))
            result_list.append(json2xml(sub_obj, "\t" + line_padding))
            result_list.append("%s</%s>" % (line_padding, tag_name))

        return "\n".join(result_list)

    return "%s%s" % (line_padding, json_obj)


def generate_intelij_skaffolds_run_configurations():
    try:
        os.makedirs(f"{REPO_ROOT}/.idea/runConfigurations")
    except OSError as e:
        pass

    for filepath in glob.glob(f"{REPO_ROOT}/.idea/runConfigurations/*.xml", recursive=True):
        if "skaffold--{}".format(INTELLIJ_RUN_CONFIGURATIONS_PREFIX) in filepath and "skaffold-without-build" not in filepath:
            os.remove(filepath)
    run_configuration_template = """<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="{configuration_name}" type="google-container-tools-skaffold-run-config" factoryName="google-container-tools-skaffold-run-config-dev" show_console_on_std_err="false" show_console_on_std_out="false" kubeconfigFile="{{&quot;displayName&quot;:&quot;{kubeconfig_path}&quot;,&quot;path&quot;:&quot;{kubeconfig_path}&quot;}}">
    <option name="allowRunningInParallel" config="false" />
    <option name="buildEnvironment" config="In Cluster" />
    <option name="cleanupDeployments" config="false" />
    <option name="deployToCurrentContext" config="true" />
    <option name="deployToMinikube" config="false" />
    <option name="envVariables">
      <map>
        {env_variables}        
      </map>
    </option>
    <option name="imageRepositoryOverride" config="{registry_url}" />
    <option name="kubernetesContext" />
    <option name="mappings">
      <list>
        {debug_mapping}
      </list>
    </option>
    <option name="moduleDeploymentType" config="DEPLOY_EVERYTHING" />
    <option name="skaffoldWatchMode" config="ON_FILE_SAVE" />
    <option name="projectPathOnTarget" />
    <option name="resourceDeletionTimeoutMins" config="2" />
    <option name="selectedOptions">
      <list />
    </option>
    <option name="skaffoldConfigurationFilePath" config="{skaffold_configuration_path}" />
    <option name="skaffoldModules">
      <list />
    </option>
    <method v="2">
        <option name="RunConfigurationTask" enabled="true" run_configuration_name="{generate_skaffolds_configuration_name}" run_configuration_type="MAKEFILE_TARGET_RUN_CONFIGURATION" />
    </method>
    <option name="skaffoldNamespace" />
    <option name="skaffoldProfile" />
    <option name="statusCheck" config="true" />
    <option name="verbosity" config="DEBUG" />
  </configuration>
</component>"""

    for filepath in glob.glob(f"{GENERATED_SKAFFOLD_DIR}/**/*.yaml", recursive=True) + [
        f"{GENERATED_SKAFFOLD_TMP_DIR}/skaffold--main--all.yaml"
    ]:
        filepath = os.path.abspath(filepath)

        filename = filepath.split("/")[-1]
        if "skaffold" in filename and "skaffold-without-build" not in filename:
            skaffold_name = filename \
                .replace("skaffold-", "") \
                .replace(".yaml", "") \
                .replace("with-build-", "") \
                .replace("without-build-", "")

            if skaffold_name == "skaffold":
                skaffold_name = "all"

            dir_name = filepath.split("/")[-2].replace("generated_skaffolds_temp/", "")

            if dir_name == "generated_skaffolds_temp":
                dir_name = "deploy"

            name = INTELLIJ_RUN_CONFIGURATIONS_PREFIX + "skaffold--" + dir_name + "--" + skaffold_name
            debug_mapping = ''
            with open(filepath, 'r') as stream:
                parsed_skaffold = yaml.safe_load(stream)
                build_context = (parsed_skaffold.get('build', {}).get('artifacts', []) or [{}])[0].get("context", None)
                if build_context:
                    mapping_local_file = build_context.replace(REPO_ROOT, "$PROJECT_DIR$")
                    debug_mapping = '''
                    <debug-mapping local-file="{}" remote-file="/app" />
                    '''.format(mapping_local_file)

            write(
                f"{REPO_ROOT}/.idea/runConfigurations/skaffold--{name}.xml",
                run_configuration_template.format(
                    configuration_name=name,
                    kubeconfig_path=os.path.abspath(KUBECONFIG).replace(REPO_ROOT, "$PROJECT_DIR$"),
                    registry_url="REGISTRY_URL_HERE", # TODO: implement me
                    skaffold_configuration_path=filepath.replace(REPO_ROOT, "$PROJECT_DIR$"),
                    env_variables='\n'.join([
                        f"<entry key=\"DOCKER_BUILDKIT\" config=\"1\" />",
                        # f"<entry key=\"DOCKER_CONTEXT\" config=\"{DOCKER_CONTEXT}\" />" if DOCKER_CONTEXT else ""
                    ]),
                    debug_mapping=debug_mapping,
                    generate_skaffolds_configuration_name=f"{INTELLIJ_RUN_CONFIGURATIONS_PREFIX}generate-skaffolds",
                    # <debug-mapping local-file="$PROJECT_DIR$/bridge_app/workflows/kafka_processors" remote-file="/app" />
                )
            )

    write(
        f"{REPO_ROOT}/.idea/runConfigurations/skaffold--{INTELLIJ_RUN_CONFIGURATIONS_PREFIX}_generate_skaffolds.xml",
        f"""<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="{INTELLIJ_RUN_CONFIGURATIONS_PREFIX}generate-skaffolds" type="MAKEFILE_TARGET_RUN_CONFIGURATION" factoryName="Makefile">
    <makefile filename="{os.path.abspath(MAKEFILE_PATH).replace(REPO_ROOT, "$PROJECT_DIR$")}" target="generate-skaffolds" workingDirectory="" arguments="">
      <envs />
    </makefile>
    <method v="2" />
  </configuration>
</component>"""
    )
