jQuery(function ($) {
  const charts = $(".run-times-chart");
  if (!charts.length) {
    return;
  }

  // one range switch for all overview charts, the one above the daily chart
  const rangeButtons = $(".daily-reports-chart-range-toggle button");
  const rangeStorageKey = "dailyReportsChartRange";
  let range = localStorage.getItem(rangeStorageKey) || "days";

  function getColors() {
    var style = getComputedStyle(document.documentElement);
    return {
      min: style.getPropertyValue('--color-unchanged').trim() || "#89A54E",
      avg: style.getPropertyValue('--color-changed').trim() || "#4572A7",
      max: style.getPropertyValue('--color-noop').trim() || "#DB843D",
    };
  }

  function render(element, rows) {
    const metric = $(element).data("metric");
    const json = rows.map(function (row) {
      return {day: row.day, min: row[metric].min, avg: row[metric].avg, max: row[metric].max};
    });
    bb.generate({
      bindto: element,
      data: {
        json: json,
        keys: {x: "day", value: ["max", "avg", "min"]},
        names: {max: "Max", avg: "Average", min: "Min"},
        type: "line",
        colors: getColors(),
      },
      size: {height: 120},
      line: {connectNull: false},
      axis: {
        // MM-DD keeps the labels on one line on phones; hours are UTC, shown in local time
        // hours as "HH" stay flat down to about 20px each
        x: {type: "category", tick: {format: function (index, label) {
          return range === "today" ? moment(label).format("HH") : label.slice(5);
        }, culling: false, rotate: range === "today" && $(element).width() < 24 * 20 ? -90 : 0, multiline: false}},
        y: {
          min: 0,
          padding: {bottom: 0},
          tick: {culling: {max: 4}},
          label: {text: "Seconds", position: "outer-middle"},
        },
      },
      tooltip: {
        format: {
          value: function (value) {
            return value + " s";
          },
        },
      },
      legend: {show: true},
    });
  }

  function load() {
    $.getJSON("run_times_chart.json?range=" + range, function (data) {
      charts.each(function () {
        render(this, data.result);
      });
    });
  }

  rangeButtons.on("click", function () {
    range = $(this).data("range-value");
    load();
  });

  load();
});
