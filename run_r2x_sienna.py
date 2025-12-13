"""Test script for Sienna Parser&Exporter workflow."""

import time
from pathlib import Path
from loguru import logger
from r2x_core.store import DataStore
from r2x_sienna.config import SiennaConfig
from r2x_sienna.exporter import to_psy
from r2x_sienna.parser import SiennaParser


def time_operation(operation_name, func, *args, **kwargs):
    """Time an operation and return the result with timing info."""
    logger.info(f"Starting: {operation_name}...")
    start_time = time.time()

    try:
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logger.success(f"✓ Completed: {operation_name} in {duration:.2f} seconds")
        return result
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"✗ Failed: {operation_name} after {duration:.2f} seconds - {e}")
        raise


def run_parser(input_path, name, skip_validation):
    config = SiennaConfig(
        model_year=2029,
        system_name="Case5_PJM",
        json_path=input_path,
        scenario="Base",
        system_base_power=100.0,
        skip_validation=skip_validation,
    )
    data_store = DataStore()
    parser = time_operation(
        "Creating Sienna parser",
        lambda: SiennaParser(
            config=config, data_store=data_store, name=f"{name}", skip_validation=skip_validation
        ),
    )
    system = time_operation("Building system from JSON", parser.build_system)
    system.info()

    return parser, system, config


def run_exporter(output_path, parser, system, config):
    output_dir = Path(output_path)
    output_dir.mkdir(exist_ok=True)
    system_data = time_operation(
        "Preparing system data for export",
        lambda: {
            "system_information": parser.system_information,
            "data_information": parser.data_information,
            "component_fields": {},  # This would contain field filtering if needed
        },
    )
    output_file = output_dir / f"{name}.json"
    logger.info(f"Exporting system to: {output_file}")
    # Time the export operation
    time_operation(
        "Exporting system to PSY format",
        to_psy,
        config,  # config as first argument
        system,  # system as second argument
        system_data,  # system_data as third argument
        output_file,  # filename as fourth argument
        write_year=config.primary_model_year,  # write_year as keyword argument
    )
    logger.success(f"✓ System successfully exported to {output_file}")
    verification_start = time.time()

    # Check if time series file was also created
    h5_file = output_file.parent / f"{output_file.stem}_time_series_storage.h5"
    logger.info(f"Checking for H5 file at: {h5_file}")
    logger.debug(f"Absolute path: {h5_file.absolute()}")
    logger.debug(f"File exists check: {h5_file.exists()}")
    logger.debug(f"File is file check: {h5_file.is_file()}")

    if h5_file.exists():
        file_size = h5_file.stat().st_size / (1024 * 1024)  # Size in MB
        logger.success(f"✓ Time series data exported to {h5_file} ({file_size:.2f} MB)")
    else:
        logger.warning("No time series data exported")

    verification_time = time.time() - verification_start
    logger.success(f"File verification completed in {verification_time:.3f} seconds")


def run(name, input_path, skip_validation, run_parser_ok=True, run_exporter_ok=True):
    if run_parser_ok and run_exporter_ok:
        parser, system, config = run_parser(input_path, name, skip_validation)
        run_exporter(output_path, parser, system, config)
    elif run_parser_ok:
        parser, system, config = run_parser(input_path, name, skip_validation)
    elif run_exporter_ok:
        run_exporter(output_path, parser, system, config)
    else:
        logger.warning("Pick a valid operation to run: parser, exporter, or both.")


if __name__ == "__main__":
    logger.enable("r2x_core")
    logger.enable("r2x_sienna")

    run_parser_ok = True
    run_exporter_ok = True
    skip_validation = False
    name = "EI_PCM_EIPC_2029A"
    # input_path = f"/Users/mvelasqu/Documents/00_ERCOT_system/{name}.json"
    input_path = f"/Users/mvelasqu/Documents/02_EI_systems/Old_EI/{name}.json"
    # input_path = f"/Users/mvelasqu/Documents/marck/GDO/r2x-sienna/tests/data/{name}/{name}.json"
    # print(input_path)
    output_path = "/Users/mvelasqu/Documents/marck/GDO/r2x-sienna/output"
    total_start_time = time.time()
    run(name, input_path, skip_validation, run_parser_ok, run_exporter_ok)
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    logger.info(f"Total script duration: {total_duration:.2f} seconds")
