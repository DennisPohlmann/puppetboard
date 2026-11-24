import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import (
    request, jsonify
)
from pypuppetdb.QueryBuilder import (ExtractOperator, AndOperator,
                                     EqualsOperator, FunctionOperator,
                                     GreaterEqualOperator)
from pypuppetdb.QueryBuilder import (LessOperator)
from pypuppetdb.utils import UTC

from puppetboard.core import get_app, get_puppetdb
from puppetboard.utils import (get_or_abort)

app = get_app()
puppetdb = get_puppetdb()


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@app.route('/daily_reports_chart.json',
           defaults={'env': app.config['DEFAULT_ENVIRONMENT']})
@app.route('/<env>/daily_reports_chart.json')
def daily_reports_chart(env):
    """Return JSON data to generate a bar chart of daily runs.

    If certname is passed as GET argument, the data will target that
    node only.
    """
    certname = request.args.get('certname')
    result = get_or_abort(
        get_daily_reports_chart,
        db=puppetdb,
        env=env,
        days_number=app.config['DAILY_REPORTS_CHART_DAYS'],
        certname=certname,
        hourly=_hourly(),
    )
    return jsonify(result=result)


def _iter_dates(days_number, reverse=False):
    """Return a list of datetime pairs AB, BC, CD, ... that represent the
       24hs time ranges of today (until this midnight) and the
       previous days.
    """
    one_day = timedelta(days=1)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())
    days_list = list(today + one_day * (1 - i) for i in range(days_number + 1))
    if reverse:
        days_list.reverse()
        return zip(days_list, days_list[1:])
    return zip(days_list[1:], days_list)


def _hourly():
    """True when the chart asks for the last 24 hours by the hour (?range=today)."""
    return request.args.get('range') == 'today'


def _iter_ranges(days_number, hourly):
    """Return (label, start, end) for each bar: the last 24 hours, or the
       last N days.
    """
    if hourly:
        # the last 24 hours up to the end of this hour, labelled with the UTC
        # start of each hour so the browser can show it in local time
        one_hour = timedelta(hours=1)
        end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + one_hour
        return [((end - one_hour * h).strftime('%Y-%m-%dT%H:%M:%SZ'),
                 end - one_hour * h, end - one_hour * (h - 1)) for h in range(24, 0, -1)]
    return [(start.strftime(DATE_FORMAT), start, end)
            for start, end in _iter_dates(days_number, reverse=True)]


def _build_query(env, start, end, certname=None):
    """Build a extract query with optional certname and environment."""
    query = ExtractOperator()
    query.add_field(FunctionOperator('count'))
    query.add_field('status')
    subquery = AndOperator()
    subquery.add(GreaterEqualOperator('producer_timestamp', start))
    subquery.add(LessOperator('producer_timestamp', end))
    if certname is not None:
        subquery.add(EqualsOperator('certname', certname))
    if env != '*':
        subquery.add(EqualsOperator('environment', env))
    query.add_query(subquery)
    query.add_group_by("status")
    return query


def _format_report_data(day, query_output):
    """Format the output of the query to a simpler dict."""
    result = {'day': day, 'changed': 0, 'unchanged': 0, 'failed': 0}
    for out in query_output:
        if out['status'] == 'changed':
            result['changed'] = out['count']
        elif out['status'] == 'unchanged':
            result['unchanged'] = out['count']
        elif out['status'] == 'failed':
            result['failed'] = out['count']
    return result


def get_daily_reports_chart(db, env, days_number, certname=None, hourly=False):
    """Return the sum of each report status (changed, unchanged, failed)
       per day, for today and the previous N days.

    This information is used to present a chart.

    :param db: The puppetdb.
    :param env: Sum up the reports in this environment.
    :param days_number: How many days to sum, including today.
    :param certname: If certname is passed, only the reports of that
    certname will be added.  If certname is not passed, all reports in
    the database will be considered.
    :param hourly: Sum per hour of the last 24 hours instead of per day.
    """
    def one_range(label_range):
        label, start, end = label_range
        query = _build_query(
            env=env,
            start=start.strftime(DATETIME_FORMAT),
            end=end.strftime(DATETIME_FORMAT),
            certname=certname,
        )
        return _format_report_data(label, db._query('reports', query=query))

    # one count query per bar; run them side by side instead of one after another
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(one_range, _iter_ranges(days_number, hourly)))


# agent report metrics in the 'time' category, in seconds
RUN_TIME_METRICS = ('catalog_application', 'fact_generation')


@app.route('/run_times_chart.json',
           defaults={'env': app.config['DEFAULT_ENVIRONMENT']})
@app.route('/<env>/run_times_chart.json')
def run_times_chart(env):
    """Return JSON data for the run time charts on the overview."""
    result = get_or_abort(
        get_run_times_chart,
        db=puppetdb,
        env=env,
        days_number=app.config['DAILY_REPORTS_CHART_DAYS'],
        hourly=_hourly(),
    )
    return jsonify(result=result)


# Run time stats per UTC hour and environment: {env: {hour: {metric: [min, max, sum, count]}}}.
# Fetching every report's metrics is slow on big fleets, so each hour is fetched
# once it is over and kept; only the hours still open are asked for again.
_run_times_cache: dict = {}
_run_times_lock = threading.Lock()
# reports of an hour can still arrive a while after it ends
RUN_TIMES_SETTLE = timedelta(hours=1)
ONE_HOUR = timedelta(hours=1)


def _hour_stats(reports):
    """Min, max, sum and count of each run time metric per hour of producer_timestamp."""
    hours = {}
    for report in reports:
        hour = datetime.fromisoformat(report['producer_timestamp']).replace(minute=0, second=0, microsecond=0)
        stats = hours.setdefault(hour, {})
        for metric in (report.get('metrics') or {}).get('data') or []:
            name = metric.get('name')
            if metric.get('category') == 'time' and name in RUN_TIME_METRICS:
                value = metric['value']
                seen = stats.get(name)
                stats[name] = ([min(seen[0], value), max(seen[1], value), seen[2] + value, seen[3] + 1]
                               if seen else [value, value, value, 1])
    return hours


def _format_run_times(day, hour_stats):
    """Min, max and mean of each run time metric over the given hours."""
    result = {'day': day}
    for name in RUN_TIME_METRICS:
        seen = [stats[name] for stats in hour_stats if name in stats]
        # None leaves a gap in the chart instead of a fake zero
        result[name] = {
            'min': round(min(s[0] for s in seen), 2) if seen else None,
            'max': round(max(s[1] for s in seen), 2) if seen else None,
            'avg': round(sum(s[2] for s in seen) / sum(s[3] for s in seen), 2) if seen else None,
        }
    return result


def _fetch_hours(db, env, start, end):
    """Run time stats of each hour from start to end, empty hours included."""
    query = ExtractOperator()
    query.add_field('producer_timestamp')
    query.add_field('metrics')
    subquery = AndOperator()
    subquery.add(GreaterEqualOperator('producer_timestamp', start.strftime(DATETIME_FORMAT)))
    subquery.add(LessOperator('producer_timestamp', end.strftime(DATETIME_FORMAT)))
    if env != '*':
        subquery.add(EqualsOperator('environment', env))
    query.add_query(subquery)
    found = _hour_stats(db._query('reports', query=query))
    hours = {}
    hour = start
    while hour < end:
        hours[hour] = found.get(hour, {})
        hour += ONE_HOUR
    return hours


def get_run_times_chart(db, env, days_number, hourly=False):
    """Return min, max and mean of the catalog application and fact
       generation time over all agent reports, per day, for today and the
       previous N days, or per hour of the last 24 hours when hourly is set.
    """
    ranges = _iter_ranges(days_number, hourly)
    now = datetime.now(timezone.utc)
    # one request at a time fills the cache, so a reload waits for it instead of asking again
    with _run_times_lock:
        cache = _run_times_cache.setdefault(env, {})
        # both views share the cache, keep what the day view needs
        oldest = now - timedelta(days=days_number + 1)
        for hour in [hour for hour in cache if hour < oldest]:
            del cache[hour]

        # spans of consecutive hours that are not cached, at most a day each
        spans = []
        hour = ranges[0][1].astimezone(timezone.utc)
        while hour < min(ranges[-1][2], now):
            if hour not in cache:
                if spans and spans[-1][1] == hour and spans[-1][1] - spans[-1][0] < ONE_HOUR * 24:
                    spans[-1][1] = hour + ONE_HOUR
                else:
                    spans.append([hour, hour + ONE_HOUR])
            hour += ONE_HOUR

        hours = dict(cache)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for fetched in pool.map(lambda span: _fetch_hours(db, env, *span), spans):
                hours.update(fetched)
                cache.update((hour, stats) for hour, stats in fetched.items()
                             if hour + ONE_HOUR + RUN_TIMES_SETTLE <= now)

    return [_format_run_times(label, [stats for hour, stats in hours.items() if start <= hour < end])
            for label, start, end in ranges]
