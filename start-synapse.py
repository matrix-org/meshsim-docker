#!/usr/local/bin/python

import jinja2
import os
import sys
import subprocess
import glob
import codecs
import time

# Utility functions
convert = lambda src, dst, environ: open(dst, "w").write(jinja2.Template(open(src).read()).render(**environ))

def check_arguments(environ, args):
    for argument in args:
        if argument not in environ:
            print("Environment variable %s is mandatory, exiting." % argument)
            sys.exit(2)

def generate_secrets(environ, secrets):
    for name, secret in secrets.items():
        if secret not in environ:
            filename = "/data/%s.%s.key" % (environ["SYNAPSE_SERVER_NAME"], name)
            if os.path.exists(filename):
                with open(filename) as handle: value = handle.read()
            else:
                print("Generating a random secret for {}".format(name))
                value = codecs.encode(os.urandom(32), "hex").decode()
                with open(filename, "w") as handle: handle.write(value)
            environ[secret] = value

# Prepare the configuration
mode = sys.argv[1] if len(sys.argv) > 1 else None
environ = os.environ.copy()

for e in environ:
    print("%s:%s" % (e, environ[e]))

ownership = "{}:{}".format(environ.get("UID", 991), environ.get("GID", 991))
args = ["python", "-m", "synapse.app.homeserver"]

# In generate mode, generate a configuration, missing keys, then exit
if mode == "generate":
    check_arguments(environ, ("SYNAPSE_SERVER_NAME", "SYNAPSE_REPORT_STATS", "SYNAPSE_CONFIG_PATH"))
    args += [
        "--server-name", environ["SYNAPSE_SERVER_NAME"],
        "--report-stats", environ["SYNAPSE_REPORT_STATS"],
        "--config-path", environ["SYNAPSE_CONFIG_PATH"],
        "--generate-config"
    ]
    os.execv("/usr/local/bin/python", args)

# In normal mode, generate missing keys if any, then run synapse
else:
    # Parse the configuration file
    if "SYNAPSE_CONFIG_PATH" in environ:
        args += ["--config-path", environ["SYNAPSE_CONFIG_PATH"]]
    else:
        check_arguments(environ, ("SYNAPSE_SERVER_NAME", "SYNAPSE_REPORT_STATS"))
        generate_secrets(environ, {
            "registration": "SYNAPSE_REGISTRATION_SHARED_SECRET",
            "macaroon": "SYNAPSE_MACAROON_SECRET_KEY"
        })
        environ["SYNAPSE_APPSERVICES"] = glob.glob("/data/appservices/*.yaml")
        if not os.path.exists("/compiled"): os.mkdir("/compiled")
        convert("/conf/homeserver.yaml", "/compiled/homeserver.yaml", environ)
        convert("/conf/log.config", "/compiled/log.config", environ)
        subprocess.check_output(["chown", "-R", ownership, "/data"])
        args += ["--config-path", "/compiled/homeserver.yaml"]
    # Generate missing keys and start synapse
    subprocess.check_output(args + ["--generate-keys"])

    # we register our test users in add_accounts.sh now to avoid having to wait for HS launch
    #os.system("(sleep 10; /usr/local/bin/register_new_matrix_user -u matthew -p secret -c /compiled/homeserver.yaml -a) &");

    os.execv("/usr/local/bin/python", args)

