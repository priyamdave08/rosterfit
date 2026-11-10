#!/usr/bin/env python3
"""CDK entry point.

    cd infra
    cdk synth                         # render CloudFormation (no AWS calls)
    cdk deploy                        # data lake + nightly refresh
    cdk deploy -c deploy_app=true     # ...plus the hosted dashboard
"""
import os
import sys
from pathlib import Path

import aws_cdk as cdk

sys.path.insert(0, str(Path(__file__).parent))
from stack import RosterFitStack  # noqa: E402

app = cdk.App()
RosterFitStack(
    app, "RosterFit",
    deploy_app=str(app.node.try_get_context("deploy_app")).lower() == "true",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
                        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
)
app.synth()
