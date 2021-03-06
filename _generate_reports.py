# Import required libraries
## Note: requires installation via pip:
##    pip install descartes fpdf2
import argparse
import json
import os

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

# import and set up functions
import _data_setup
import _report_functions
from batlow import batlow_map

# Set up commandline input parsing


parser = argparse.ArgumentParser(
    description="Scorecards for the Global Healthy and Sustainable Cities Indicator Collaboration Study"
)

parser.add_argument(
    "--cities",
    default="Maiduguri,Mexico City,Baltimore,Phoenix,Seattle,Sao Paulo,Hong Kong,Chennai,Bangkok,Hanoi,Graz,Ghent,Bern,Olomouc,Cologne,Odense,Barcelona,Valencia,Vic,Belfast,Lisbon,Adelaide,Melbourne,Sydney,Auckland",
    help=(
        "A list of cities, for example: Baltimore, Phoenix, Seattle, Adelaide, Melbourne, "
        "Sydney, Auckland, Bern, Odense, Graz, Cologne, Ghent, Belfast, Barcelona, Valencia, Vic, "
        "Lisbon, Olomouc, Hong, Kong, Mexico City, Sao, Paulo, Bangkok, Hanoi, Maiduguri, Chennai"
    ),
)

parser.add_argument(
    "--generate_resources",
    action="store_true",
    default=False,
    help="Generate images from input data for each city? Default is False.",
)

parser.add_argument(
    "--language",
    default="English",
    type=str,
    help="The desired language for presentation, as defined in the template workbook languages sheet.",
)

parser.add_argument(
    "--auto_language",
    action="store_true",
    default=False,
    help="Identify all languages associated with specified cities and prepare reports for these.",
)

parser.add_argument(
    "--by_city",
    action="store_true",
    default=True,
    help="Save reports in city-specific sub-folders.",
)

parser.add_argument(
    "--by_language",
    action="store_true",
    default=True,
    help="Save reports in language-specific sub-folders (default).",
)

parser.add_argument(
    "--templates",
    default="web",
    help=(
        'A list of templates to iterate outputs over, for example: "web" (default), or "web,print"\n'
        'The words listed correspond to sheets present in the configuration file, prefixed by "template_",'
        'for example, "template_web" and "template_print".  These files contain the PDF template layout '
        "information required by fpdf2 for pagination of the output PDF files."
    ),
)

parser.add_argument(
    "--configuration",
    default="_report_configuration.xlsx",
    help=(
        "An XLSX workbook containing spreadsheets detailing template layout(s), prose, fonts and city details "
        "to be drawn upon when formatting reports."
    ),
)


config = parser.parse_args()
all_cities = [x.strip() for x in config.cities.split(",")]
templates = [f"template_{x.strip()}" for x in config.templates.split(",")]
cmap = batlow_map

if __name__ == "__main__":
    # load city parameters
    with open(_data_setup.city_json_data) as f:
        city_data = json.load(f)

    configuration_file = config.configuration
    # Run all specified language-city permutations if auto-language detection
    if config.auto_language:
        languages = pd.read_excel(configuration_file, sheet_name="languages")
        languages = languages.query(f"name in {all_cities}").dropna(
            axis=1, how="all"
        )
        languages = languages[languages.columns[1:]].set_index("name")
        # replace all city name variants with English equivalent for grouping purposes
        for city in languages.index:
            languages.loc[city][languages.loc[city].notnull()] = city

        languages = (
            languages[languages.columns]
            .transpose()
            .stack()
            .groupby(level=0)
            .apply(list)
        )
    else:
        languages = pd.Series([all_cities], index=[config.language])

    # if non-default language is specified along with auto_language, only prepare cities for that language
    if config.language != "English":
        language_list = [config.language]
    else:
        language_list = languages.index

    for language in language_list:
        print(f"\n{language} language reports:")
        cities = languages[language]
        # set up fonts
        fonts = pd.read_excel(configuration_file, sheet_name="fonts")
        if (
            language.replace(" (Auto-translation)", "")
            in fonts.Language.unique()
        ):
            fonts = fonts.loc[
                fonts["Language"]
                == language.replace(" (Auto-translation)", "")
            ].fillna("")
        else:
            fonts = fonts.loc[fonts["Language"] == "default"].fillna("")

        main_font = fonts.File.values[0].strip()
        fm.fontManager.addfont(main_font)
        prop = fm.FontProperties(fname=main_font)
        fm.findfont(prop=prop, directory=main_font, rebuild_if_missing=True)
        plt.rcParams["font.family"] = prop.get_name()
        font = fonts.Font.values[0]
        # Set up main city indicators
        df = pd.read_csv(_data_setup.csv_city_indicators)
        df.set_index("City", inplace=True)
        vars = {
            "pop_pct_access_500m_fresh_food_market_score": "Food market",
            "pop_pct_access_500m_convenience_score": "Convenience",
            "pop_pct_access_500m_public_open_space_any_score": "Any public open space",
            "pop_pct_access_500m_public_open_space_large_score": "Large public open space",
            "pop_pct_access_500m_pt_any_score": "Public transport stop",
            "pop_pct_access_500m_pt_gtfs_freq_20_score": "Public transport with regular service",
        }
        df = df.rename(columns=vars)
        indicators = vars.values()

        # Set up thresholds
        threshold_lookup = {
            "Mean 1000 m neighbourhood population per km??": {
                "title": "Neighbourhood population density (per km??)",
                "field": "local_nh_population_density",
                "scale": "log",
            },
            "Mean 1000 m neighbourhood street intersections per km??": {
                "title": "Neighbourhood intersection density (per km??)",
                "field": "local_nh_intersection_density",
                "scale": "log",
            },
        }

        # Set up indicator min max summaries
        df_extrema = pd.read_csv(_data_setup.csv_hex_indicators)
        df_extrema.set_index("City", inplace=True)
        for k in threshold_lookup:
            threshold_lookup[k]["range"] = (
                df_extrema[threshold_lookup[k]["field"]]
                .describe()[["min", "max"]]
                .astype(int)
                .values
            )

        threshold_scenarios = _report_functions.setup_thresholds(
            _data_setup.csv_thresholds_data, threshold_lookup
        )

        # Set up between city averages comparisons
        comparisons = {}
        comparisons["access"] = {}
        comparisons["access"]["p25"] = df[indicators].quantile(q=0.25)
        comparisons["access"]["p50"] = df[indicators].median()
        comparisons["access"]["p75"] = df[indicators].quantile(q=0.75)

        # Generate placeholder hero images, if not existing
        # if not os.path.exists('hero_images/{city}.png'):

        df_policy = _report_functions.policy_data_setup(
            policy_lookup=_data_setup.policy_lookup
        )

        walkability_stats = pd.read_csv(
            _data_setup.csv_walkability_data, index_col="City"
        )

        # Loop over cities
        successful = 0
        for city in cities:
            print(f"\n- {city}"),
            try:
                year = 2020
                city_policy = {}
                for policy_analysis in _data_setup.policy_lookup["analyses"]:
                    city_policy[policy_analysis] = df_policy[
                        policy_analysis
                    ].loc[city]
                    if policy_analysis in ["Presence", "Checklist"]:
                        city_policy[f"{policy_analysis}_rating"] = df_policy[
                            f"{policy_analysis}_rating"
                        ].loc[city]
                        city_policy[f"{policy_analysis}_global"] = df_policy[
                            f"{policy_analysis}_rating"
                        ].describe()

                city_policy["Presence_gdp"] = df_policy["Presence_gdp"]
                threshold_scenarios["walkability"] = walkability_stats.loc[
                    city, "pct_walkability_above_median"
                ]
                # set up phrases
                phrases = _report_functions.prepare_phrases(
                    configuration_file, city, language
                )

                # Generate resources
                if config.generate_resources:
                    capture_return = _report_functions.generate_resources(
                        city,
                        phrases,
                        _data_setup.gpkg_hexes,
                        df,
                        indicators,
                        comparisons,
                        threshold_scenarios,
                        city_policy,
                        configuration_file,
                        language,
                        cmap,
                    )

                # instantiate template
                for template in templates:
                    print(f" [{template}]")
                    capture_return = _report_functions.generate_scorecard(
                        city,
                        phrases,
                        threshold_scenarios=threshold_scenarios,
                        city_policy=city_policy,
                        configuration_file=configuration_file,
                        template_sheet=template,
                        language=language,
                        font=font,
                        by_city=config.by_city,
                        by_language=config.by_language,
                    )

                successful += 1
            except Exception as e:
                print(f"\t- Report generation failed with error: {e}")

        print(f"\n {successful}/{len(cities)} cities processed successfully!")
