"""Configuration for Sienna parser."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from r2x_core.plugin_config import PluginConfig


class SiennaConfig(PluginConfig):
    """Configuration for Sienna model parser.

    This configuration class defines all parameters needed to parse
    Sienna model data, including year information and model-specific settings.
    Model-specific defaults and constants should be loaded using the
    `load_defaults()` class method and used in parser logic.

    Parameters
    ----------
    model_year : int | list[int]
        Model solve year(s) (e.g., 2030, [2030, 2040, 2050])
    system_name : str, optional
        Name of the power system
    scenario : str, optional
        Scenario identifier
    system_base_power : float, optional
        System base power in MVA for per-unit calculations
    skip_validation : bool, optional
        Whether to skip validation during parsing

    Examples
    --------
    Single year with custom base power:

    >>> config = SiennaConfig(
    ...     model_year=2030,
    ...     system_name="EI_Sys",
    ...     system_base_power=100.0,
    ...     skip_validation=True,
    ... )

    Multiple years:

    >>> config = SiennaConfig(
    ...     model_year=[2030, 2040, 2050],
    ...     system_name="Case5_PJM",
    ...     skip_validation=False,
    ... )

    See Also
    --------
    r2x_core.plugin_config.PluginConfig : Base configuration class
    r2x_sienna.parser.SiennaParser : Parser that uses this configuration
    load_defaults : Class method to load default constants from JSON
    """

    model_year: Annotated[
        int | list[int] | None,
        Field(description="Model solve year(s) - automatically converted to list"),
    ] = None
    system_name: Annotated[str | None, Field(default=None, description="Power system name")] = None
    json_path: Annotated[str | None, Field(default=None, description="Path to JSON data file")] = None
    scenario: Annotated[str, Field(default="base", description="Scenario identifier")] = "base"
    system_base_power: Annotated[
        float, Field(default=100.0, description="System base power in MVA for per-unit calculations")
    ] = 100.0
    skip_validation: Annotated[
        bool, Field(default=False, description="Whether to skip validation during parsing")
    ] = False
