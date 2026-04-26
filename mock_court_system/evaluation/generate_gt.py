import yaml
import os
from converters.cd_converter import CDConverter
from converters.dd_converter import DDConverter
from converters.ci_converter import CIConverter

def load_config(config_path="evaluation/eval_config.yaml"):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    paths = config['evaluation']['paths']
    
    # CD Conversion
    print("Converting CD Data...")
    cd_conv = CDConverter(
        dialog_dir=paths['raw_data']['cd_dialog'],
        doc_dir=paths['raw_data']['cd_doc']
    )
    cd_conv.convert(paths['ground_truth']['cd'], "CD")
    
    # DD Conversion
    print("Converting DD Data...")
    dd_conv = DDConverter(
        dialog_dir=paths['raw_data']['dd_dialog'],
        doc_dir=paths['raw_data']['dd_doc']
    )
    dd_conv.convert(paths['ground_truth']['dd'], "DD")
    
    # CI Conversion
    print("Converting CI Data...")
    ci_conv = CIConverter(
        dialog_dir=paths['raw_data']['ci_dialog'],
        doc_dir=paths['raw_data']['ci_doc']
    )
    ci_conv.convert(paths['ground_truth']['ci'], "CI")
    
    print("All conversions completed.")

if __name__ == "__main__":
    main()




