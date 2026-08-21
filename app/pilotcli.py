# Copyright 2022 Indoc Research
# 
# Licensed under the EUPL, Version 1.2 or – as soon they
# will be approved by the European Commission - subsequent
# versions of the EUPL (the "Licence");
# You may not use this work except in compliance with the
# Licence.
# You may obtain a copy of the Licence at:
# 
# https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12
# 
# Unless required by applicable law or agreed to in
# writing, software distributed under the Licence is
# distributed on an "AS IS" basis,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied.
# See the Licence for the specific language governing
# permissions and limitations under the Licence.
# 

import click
import requests
import app.services.output_manager.error_handler as error_handler
from app.commands.entry_point import entry_point
from app.utils.aggregated import doc
from app.services.output_manager.help_page import update_message
from app.commands.entry_point import command_groups

class ComplexCLI(click.MultiCommand):
    def list_commands(self, ctx):
        rv = command_groups()
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        try:
            mod = __import__(f"app.commands.{name}", None, None, ['cli'])
        except ImportError:
            return
        return mod.cli


@click.command(cls=ComplexCLI)
@doc(update_message)
def cli():
    try:
        entry_point()
    except requests.exceptions.ConnectionError:
        error_handler.SrvErrorHandler.customized_handle(error_handler.ECustomizedError.ERROR_CONNECTION, True)
    except Exception as e:
        error_handler.SrvErrorHandler.default_handle(e, True)


if __name__ == '__main__':
    cli()
