jQuery(function ($) {
  const charts = $(".run-times-chart");
  if (!charts.length) {
    return;
  }

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
      size: {height: 200},
      line: {connectNull: false},
      axis: {
        // MM-DD keeps the labels on one line on phones
        x: {type: "category", tick: {format: function (index, day) { return day.slice(5); }}},
        y: {
          min: 0,
          padding: {bottom: 0},
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

  $.getJSON("run_times_chart.json", function (data) {
    charts.each(function () {
      render(this, data.result);
    });
  });
});
