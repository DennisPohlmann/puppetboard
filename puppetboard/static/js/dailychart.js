jQuery(function ($) {
  const chartElement = $("#dailyReportsChart");
  const toggleButtons = $(".daily-reports-chart-mode-toggle button");
  const chartModeStorageKey = "dailyReportsChartMode";
  const rangeButtons = $(".daily-reports-chart-range-toggle button");
  const rangeStorageKey = "dailyReportsChartRange";
  let url = "daily_reports_chart.json";
  let certname = chartElement.data("certname");
  let days = parseInt(chartElement.data("days"));
  let chartMode = localStorage.getItem(chartModeStorageKey) || chartElement.data("chart-mode") || "stacked";
  let range = localStorage.getItem(rangeStorageKey) || "days";
  let chart = null;
  let chartData = null;
  let defaultJSON = emptyData(range);

  // zero bars until the data is there: one per day, or per hour of the last 24 hours
  function emptyData(range) {
    let rows = [];
    for (let index = (range === "today" ? 23 : days - 1); index >= 0; index--) {
      rows.push({
        day: range === "today"
          ? moment.utc().startOf('hour').subtract(index, 'hours').format('YYYY-MM-DDTHH:mm:ss[Z]')
          : moment().startOf('day').subtract(index, 'days').format('YYYY-MM-DD'),
        unchanged: 0,
        changed: 0,
        failed: 0
      });
    }
    return rows;
  }

  // hourly labels are UTC hour starts; show them as local clock time
  function xTick(index, label) {
    return range === "today" ? moment(label).format("HH:mm") : label;
  }

  // Get chart colors from CSS variables (supports dark mode)
  function getChartColors() {
    var style = getComputedStyle(document.documentElement);
    return {
      failed: style.getPropertyValue('--color-failed').trim() || "#AA4643",
      changed: style.getPropertyValue('--color-changed').trim() || "#4572A7",
      unchanged: style.getPropertyValue('--color-unchanged').trim() || "#89A54E",
    };
  }

  // Small counts produce fractional ticks; label whole numbers only
  function integerTick(value) {
    return Number.isInteger(value) ? value : "";
  }

  function getChartConfig(mode) {
    let splitMode = mode === "split";

    return {
      bindto: "#dailyReportsChart",
      data: {
        json: defaultJSON,
        keys: {
          x: "day",
          value: ["failed", "changed", "unchanged"],
        },
        type: splitMode ? undefined : "bar",
        types: splitMode ? {
          unchanged: "bar",
          changed: "spline",
          failed: "spline",
        } : undefined,
        groups: splitMode ? undefined : [["failed", "changed", "unchanged"]],
        axes: splitMode ? {
          unchanged: "y",
          changed: "y2",
          failed: "y2",
        } : undefined,
        labels: splitMode ? {
          format: function(value, id) {
            if ((id === "changed" || id === "failed") && value > 0 && value < 1000) {
              return Math.round(value);
            }

            return "";
          },
        } : undefined,
        colors: getChartColors(),
      },
      size: {
        height: splitMode ? 220 : 160,
      },
      point: splitMode ? {
        r: 3,
      } : undefined,
      spline: {
        // Monotone keeps the curve from dipping below zero between points
        interpolation: {
          type: "monotone-x",
        },
      },
      axis: {
        x: {
          type: "category",
          tick: {
            format: xTick,
            // 24 hourly labels do not fit on a phone; show every few
            culling: range === "today" ? {max: 8} : false,
            multiline: range !== "today",
          },
        },
        y: splitMode ? {
          label: {
            text: "Unchanged",
            position: "outer-middle",
          },
          min: 0,
          padding: {bottom: 0},
          tick: {
            format: integerTick,
          },
        } : {
          tick: {
            culling: {max: 6},
          },
        },
        y2: splitMode ? {
          show: true,
          label: {
            text: "Changed / Failed",
            position: "outer-middle",
          },
          min: 0,
          padding: {bottom: 0},
          tick: {
            format: integerTick,
          },
        } : undefined,
      },
      legend: {
        show: true,
      },
    };
  }

  function updateModeButtons(mode) {
    toggleButtons.removeClass("active");
    toggleButtons.filter("[data-chart-mode-value='" + mode + "']").addClass("active");
    rangeButtons.removeClass("active");
    rangeButtons.filter("[data-range-value='" + range + "']").addClass("active");
  }

  function renderChart(mode, data) {
    if (chart) {
      chart.destroy();
    }

    chart = bb.generate(getChartConfig(mode));
    chart.load({json: data || defaultJSON});
    updateModeButtons(mode);
  }

  if (typeof certname !== typeof undefined && certname !== false) {
    // truncate /node/certname from URL, to determine path to json
    url =
      window.location.href.replace(/\/node\/[^/]+$/, "") +
      "/daily_reports_chart.json?certname=" +
      certname
  }

  function load() {
    $.getJSON(url + (url.indexOf("?") < 0 ? "?" : "&") + "range=" + range, function(data) {
      chartData = data.result;
      renderChart(chartMode, chartData);
    });
  }

  rangeButtons.on("click", function() {
    range = $(this).data("range-value");
    localStorage.setItem(rangeStorageKey, range);
    defaultJSON = emptyData(range);
    chartData = null;
    renderChart(chartMode, defaultJSON);
    load();
  });

  toggleButtons.on("click", function() {
    chartMode = $(this).data("chart-mode-value");
    localStorage.setItem(chartModeStorageKey, chartMode);
    renderChart(chartMode, chartData || defaultJSON);
  });

  renderChart(chartMode, defaultJSON);
  load();
})
