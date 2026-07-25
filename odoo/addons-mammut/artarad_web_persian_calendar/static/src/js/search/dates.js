/** @odoo-module **/
import * as search_dates from "@web/search/utils/dates";
import { QUARTERS } from "@web/search/utils/dates";

import { _lt } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import { serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";

const jMONTH_OPTIONS = {
    this_month: {
        id: "month",
        groupNumber: 1,
        format: "jMMMM",
        plusParam: {},
        granularity: "jmonth",
    },
    last_month: {
        id: "month-1",
        groupNumber: 1,
        format: "jMMMM",
        plusParam: { jmonths: -1 },
        granularity: "jmonth",
    },
    antepenultimate_month: {
        id: "month-2",
        groupNumber: 1,
        format: "jMMMM",
        plusParam: { jmonths: -2 },
        granularity: "jmonth",
    },
};

const jQUARTER_OPTIONS = {
    fourth_quarter: {
        id: "fourth_quarter",
        groupNumber: 1,
        description: QUARTERS[4].description,
        setParam: { jquarter: 4 },
        granularity: "jquarter",
    },
    third_quarter: {
        id: "third_quarter",
        groupNumber: 1,
        description: QUARTERS[3].description,
        setParam: { jquarter: 3 },
        granularity: "jquarter",
    },
    second_quarter: {
        id: "second_quarter",
        groupNumber: 1,
        description: QUARTERS[2].description,
        setParam: { jquarter: 2 },
        granularity: "jquarter",
    },
    first_quarter: {
        id: "first_quarter",
        groupNumber: 1,
        description: QUARTERS[1].description,
        setParam: { jquarter: 1 },
        granularity: "jquarter",
    },
};

const jYEAR_OPTIONS = {
    this_year: {
        id: "year",
        groupNumber: 2,
        format: "jyyyy",
        plusParam: {},
        granularity: "jyear",
    },
    last_year: {
        id: "year-1",
        groupNumber: 2,
        format: "jyyyy",
        plusParam: { jyears: -1 },
        granularity: "jyear",
    },
    antepenultimate_year: {
        id: "year-2",
        groupNumber: 2,
        format: "jyyyy",
        plusParam: { jyears: -2 },
        granularity: "jyear",
    },
};

const MONTH_OPTIONS = {
    this_month: {
        id: "month",
        groupNumber: 1,
        format: "MMMM",
        plusParam: {},
        granularity: "month",
    },
    last_month: {
        id: "month-1",
        groupNumber: 1,
        format: "MMMM",
        plusParam: { months: -1 },
        granularity: "month",
    },
    antepenultimate_month: {
        id: "month-2",
        groupNumber: 1,
        format: "MMMM",
        plusParam: { months: -2 },
        granularity: "month",
    },
};

const QUARTER_OPTIONS = {
    fourth_quarter: {
        id: "fourth_quarter",
        groupNumber: 1,
        description: QUARTERS[4].description,
        setParam: { quarter: 4 },
        granularity: "quarter",
    },
    third_quarter: {
        id: "third_quarter",
        groupNumber: 1,
        description: QUARTERS[3].description,
        setParam: { quarter: 3 },
        granularity: "quarter",
    },
    second_quarter: {
        id: "second_quarter",
        groupNumber: 1,
        description: QUARTERS[2].description,
        setParam: { quarter: 2 },
        granularity: "quarter",
    },
    first_quarter: {
        id: "first_quarter",
        groupNumber: 1,
        description: QUARTERS[1].description,
        setParam: { quarter: 1 },
        granularity: "quarter",
    },
};

const YEAR_OPTIONS = {
    this_year: {
        id: "year",
        groupNumber: 2,
        format: "yyyy",
        plusParam: {},
        granularity: "year",
    },
    last_year: {
        id: "year-1",
        groupNumber: 2,
        format: "yyyy",
        plusParam: { years: -1 },
        granularity: "year",
    },
    antepenultimate_year: {
        id: "year-2",
        groupNumber: 2,
        format: "yyyy",
        plusParam: { years: -2 },
        granularity: "year",
    },
};

function getCustomPeriodOptions(optionsParams) {
    const { customOptions } = optionsParams;
    return customOptions.map((option) => ({
        id: option.id,
        description: option.description,
        granularity: "withDomain",
        groupNumber: 3,
        domain: option.domain,
    }));
}

search_dates.PERIOD_OPTIONS = odoo.user_calendar_type === "jalaali"
? Object.assign({}, jMONTH_OPTIONS, jQUARTER_OPTIONS, jYEAR_OPTIONS)
: Object.assign({}, MONTH_OPTIONS, QUARTER_OPTIONS, YEAR_OPTIONS)
;

search_dates.getSetParam = function (periodOption, referenceMoment) {
    ////////// overrided //////////
    // if (periodOption.granularity === "quarter") {
    if (periodOption.granularity.replace("j", "") === "quarter") {
    ////////// ///////// //////////
        return periodOption.setParam;
    }
    const date = referenceMoment.plus(periodOption.plusParam);
    const granularity = periodOption.granularity;
    const setParam = { [granularity]: date[granularity] };
    return setParam;
}

search_dates.getSelectedOptions = function (referenceMoment, searchItem, selectedOptionIds) {
    ////////// Overrided //////////
    // const selectedOptions = { year: [] };
    const selectedOptions = odoo.user_calendar_type === "jalaali" ? { jyear: [] } : { year: [] };
    ////////// ///////// //////////
    ////////// Overrided //////////
    // const periodOptions = getPeriodOptions(referenceMoment, searchItem.optionsParams);
    const periodOptions = Object.assign({}, search_dates.PERIOD_OPTIONS, getCustomPeriodOptions(searchItem.optionsParams));
    ////////// ///////// //////////
    for (const optionId of selectedOptionIds) {
        const option = Object.values(periodOptions).find((option) => option.id === optionId);
        const setParam = search_dates.getSetParam(option, referenceMoment);
        const granularity = option.granularity;
        if (!selectedOptions[granularity]) {
            selectedOptions[granularity] = [];
        }
        selectedOptions[granularity].push({ granularity, setParam });
    }
    return selectedOptions;
}

search_dates.getPeriodOptions = function(referenceMoment) {
    // adapt when solution for moment is found...
    const options = [];
    const originalOptions = Object.values(search_dates.PERIOD_OPTIONS);
    for (const option of originalOptions) {
        const { id, groupNumber } = option;
        let description;
        let defaultYear;
        ////////// overrided //////////
        // switch (option.granularity) {
        switch (option.granularity.replace("j", "")) {
        ////////// ///////// //////////
            case "quarter":
                description = option.description.toString();
                ////////// overrided //////////
                // defaultYear = referenceMoment.set(option.setParam).year;
                defaultYear = odoo.user_calendar_type === "jalaali" ? referenceMoment.set(option.setParam).jyear : referenceMoment.set(option.setParam).year;
                ////////// ///////// //////////
                break;
            case "month":
            case "year": {
                const date = referenceMoment.plus(option.plusParam);
                description = date.toFormat(option.format);
                ////////// overrided //////////
                // defaultYear = date.year;
                defaultYear = odoo.user_calendar_type === "jalaali" ? date.jyear : date.year;
                ////////// ///////// //////////
                break;
            }
        }
        const setParam = search_dates.getSetParam(option, referenceMoment);
        options.push({ id, groupNumber, description, defaultYear, setParam });
    }
    const periodOptions = [];
    for (const option of options) {
        const { id, groupNumber, description, defaultYear } = option;
        ////////// overrided //////////
        // const yearOption = options.find((o) => o.setParam && o.setParam.year === defaultYear);
        const yearOption = odoo.user_calendar_type === "jalaali"
                            ? options.find((o) => o.setParam && o.setParam.jyear === defaultYear)
                            : options.find((o) => o.setParam && o.setParam.year === defaultYear);
        ////////// ///////// //////////
        periodOptions.push({
            id,
            groupNumber,
            description,
            defaultYearId: yearOption.id,
        });
    }
    return periodOptions;
}

search_dates.getComparisonParams = function(referenceMoment, searchItem, selectedOptionIds, comparisonOptionId) {
    const comparisonOption = search_dates.COMPARISON_OPTIONS[comparisonOptionId];
    const selectedOptions = search_dates.getSelectedOptions(referenceMoment, searchItem, selectedOptionIds);
    if (comparisonOption.plusParam) {
        return [comparisonOption.plusParam, selectedOptions];
    }
    const plusParam = {};
    let globalGranularity = "year";
    if (selectedOptions.month) {
        globalGranularity = "month";
    } else if (selectedOptions.quarter) {
        globalGranularity = "quarter";
    }
    ////////// Overrided //////////
    if (odoo.user_calendar_type === "jalaali") {
        globalGranularity = 'jyear';
        if (selectedOptions.jmonth) {
            globalGranularity = 'jmonth';
        } else if (selectedOptions.jquarter) {
            globalGranularity = 'jquarter';
        }
    }
    ////////// ///////// //////////
    const granularityFactor = PER_YEAR[globalGranularity];
    ////////// Overrided //////////
    // const years = selectedOptions.year.map(o => o.setParam.year);
    const years = odoo.user_calendar_type === "jalaali" ? selectedOptions.jyear.map(o => o.setParam.jyear) : selectedOptions.year.map(o => o.setParam.year);
    ////////// ///////// //////////
    const yearMin = Math.min(...years);
    const yearMax = Math.max(...years);
    let optionMin = 0;
    let optionMax = 0;
    if (selectedOptions.quarter) {
        const quarters = selectedOptions.quarter.map((o) => o.setParam.quarter);
        if (globalGranularity === "month") {
            delete selectedOptions.quarter;
            for (const quarter of quarters) {
                for (const month of QUARTERS[quarter].coveredMonths) {
                    const monthOption = selectedOptions.month.find(
                        (o) => o.setParam.month === month
                    );
                    if (!monthOption) {
                        selectedOptions.month.push({
                            setParam: { month },
                            granularity: "month",
                        });
                    }
                }
            }
        } else {
            optionMin = Math.min(...quarters);
            optionMax = Math.max(...quarters);
        }
    }
    ////////// Overrided //////////
    if (selectedOptions.jquarter) {
        const quarters = selectedOptions.jquarter.map(o => o.setParam.jquarter);
        if (globalGranularity === 'jmonth') {
            delete selectedOptions.jquarter;
            for (const quarter of quarters) {
                for (const month of QUARTERS[quarter].coveredMonths) {
                    const monthOption = selectedOptions.jmonth.find(
                        o => o.setParam.jmonth === month
                    );
                    if (!monthOption) {
                        selectedOptions.jmonth.push({
                            setParam: { jmonth:month, }, granularity: 'jmonth',
                        });
                    }
                }
            }
        } else {
            optionMin = Math.min(...quarters);
            optionMax = Math.max(...quarters);
        }
    }
    ////////// ///////// //////////
    if (selectedOptions.month) {
        const months = selectedOptions.month.map((o) => o.setParam.month);
        optionMin = Math.min(...months);
        optionMax = Math.max(...months);
    }
    ////////// Overrided //////////
    if (selectedOptions.jmonth) {
        const months = selectedOptions.jmonth.map(o => o.setParam.jmonth);
        optionMin = Math.min(...months);
        optionMax = Math.max(...months);
    }
    ////////// ///////// //////////
    const num = -1 + granularityFactor * (yearMin - yearMax) + optionMin - optionMax;
    const key =
        globalGranularity === "year"
            ? "years"
            : globalGranularity === "month"
            ? "months"
            : "quarters";
    ////////// Overrided //////////
    if (odoo.user_calendar_type === "jalaali") {
        const key =
        globalGranularity === "year"
            ? "jyears"
            : globalGranularity === "month"
            ? "jmonths"
            : "jquarters";
    }
    ////////// ///////// //////////
    plusParam[key] = num;
    return [plusParam, selectedOptions];
}

search_dates.constructDateRange = function(params) {
    const { referenceMoment, fieldName, fieldType, granularity, setParam, plusParam } = params;
    if ("quarter" in setParam) {
        // Luxon does not consider quarter key in setParam (like moment did)
        setParam.month = QUARTERS[setParam.quarter].coveredMonths[0];
        delete setParam.quarter;
    }
    ////////// Overrided //////////
    if ("jquarter" in setParam) {
        // Luxon does not consider quarter key in setParam (like moment did)
        setParam.jmonth = QUARTERS[setParam.jquarter].coveredMonths[0];
        delete setParam.jquarter;
    }
    ////////// ///////// //////////
    const date = referenceMoment.set(setParam).plus(plusParam || {});
    // compute domain
    const leftDate = date.startOf(granularity);
    const rightDate = date.endOf(granularity);
    let leftBound;
    let rightBound;
    if (fieldType === "date") {
        leftBound = serializeDate(leftDate);
        rightBound = serializeDate(rightDate);
    } else {
        leftBound = serializeDateTime(leftDate);
        rightBound = serializeDateTime(rightDate);
    }
    const domain = new Domain(["&", [fieldName, ">=", leftBound], [fieldName, "<=", rightBound]]);
    // compute description
    ////////// Overrided //////////
    // const descriptions = [date.toFormat("yyyy")];
    const descriptions = [date.toFormat(odoo.user_calendar_type === "jalaali" ? "jyyyy" : "yyyy")];
    ////////// ///////// //////////
    const method = localization.direction === "rtl" ? "push" : "unshift";
    ////////// Overrided //////////
    // if (granularity === "month") {
    //     descriptions[method](date.toFormat("MMMM"));
    // } else if (granularity === "quarter") {
    //     const quarter = date.quarter;
    //     descriptions[method](QUARTERS[quarter].description.toString());
    // }
    switch (granularity) {
        case "month":
            descriptions[method](date.toFormat("MMMM"));
            break;
        case "quarter":
            descriptions[method](QUARTERS[date.quarter].description.toString());
            break;
        case "jmonth":
            descriptions[method](date.toFormat("jMMMM"));
            break;
        case "jquarter":
            descriptions[method](QUARTERS[date.jquarter].description.toString());
            break;
    }
    ////////// ///////// //////////
    const description = descriptions.join(" ");
    return { domain, description };
}


search_dates.constructDateDomain = function(
    referenceMoment,
    searchItem,
    selectedOptionIds,
    comparisonOptionId
) {
    let plusParam;
    let selectedOptions;
    if (comparisonOptionId) {
        [plusParam, selectedOptions] = getComparisonParams(
            referenceMoment,
            searchItem,
            selectedOptionIds,
            comparisonOptionId
        );
    } else {
        selectedOptions = search_dates.getSelectedOptions(referenceMoment, searchItem, selectedOptionIds);
    }
    if ("withDomain" in selectedOptions) {
        return {
            description: selectedOptions.withDomain[0].description,
            domain: Domain.and([selectedOptions.withDomain[0].domain, searchItem.domain]),
        };
    }
    ////////// Overrided //////////
    // const yearOptions = selectedOptions.year;
    // const otherOptions = [...(selectedOptions.quarter || []), ...(selectedOptions.month || [])];
    var yearOptions = selectedOptions.year;
    var otherOptions = [...(selectedOptions.quarter || []), ...(selectedOptions.month || [])];
    if (odoo.user_calendar_type === "jalaali") {
        var yearOptions = selectedOptions.jyear;
        var otherOptions = [...(selectedOptions.jquarter || []), ...(selectedOptions.jmonth || [])];          
    }
    ////////// ///////// //////////
    search_dates.sortPeriodOptions(yearOptions);
    search_dates.sortPeriodOptions(otherOptions);
    const ranges = [];
    const { fieldName, fieldType } = searchItem;
    for (const yearOption of yearOptions) {
        const constructRangeParams = {
            referenceMoment,
            fieldName,
            fieldType,
            plusParam,
        };
        if (otherOptions.length) {
            for (const option of otherOptions) {
                const setParam = Object.assign(
                    {},
                    yearOption.setParam,
                    option ? option.setParam : {}
                );
                const { granularity } = option;
                const range = search_dates.constructDateRange(
                    Object.assign({ granularity, setParam }, constructRangeParams)
                );
                ranges.push(range);
            }
        } else {
            const { granularity, setParam } = yearOption;
            const range = search_dates.constructDateRange(
                Object.assign({ granularity, setParam }, constructRangeParams)
            );
            ranges.push(range);
        }
    }
    let domain = Domain.combine(
        ranges.map((range) => range.domain),
        "OR"
    );
    domain = Domain.and([domain, searchItem.domain]);
    const description = ranges.map((range) => range.description).join("/");
    return { domain, description };
}