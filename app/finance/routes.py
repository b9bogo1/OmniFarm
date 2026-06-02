import json
from datetime import date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from flask_babel import gettext as _

from app.models.finance import FinanceEntry, EntryType, ProductionScope
from app.auth.decorators import technician_required
from . import finance_bp
from .forms import FinanceEntryForm


@finance_bp.route('/')
@technician_required
def index():
    type_filter  = request.args.get('type', '')
    scope_filter = request.args.get('scope', '')
    month_filter = request.args.get('month', '')

    entries = FinanceEntry.find_filtered(type_filter, scope_filter, month_filter)

    total_revenue = sum(e.amount_float for e in entries if e.entry_type == EntryType.REVENUE)
    total_expense = sum(e.amount_float for e in entries if e.entry_type == EntryType.EXPENSE)
    balance       = total_revenue - total_expense

    # Monthly chart (last 6 months — always unfiltered)
    today  = date.today()
    months = []
    for i in range(5, -1, -1):
        months.append((today.replace(day=1) - timedelta(days=i * 28)).replace(day=1))

    all_rows = FinanceEntry.monthly_totals()
    monthly  = {}
    for row in all_rows:
        key = (row['_id']['yr'], row['_id']['mo'])
        monthly.setdefault(key, {})[row['_id']['type']] = float(row['total'])

    m_labels, m_revenues, m_expenses = [], [], []
    for first in months:
        m_labels.append(first.strftime('%b %Y'))
        d = monthly.get((first.year, first.month), {})
        m_revenues.append(d.get(EntryType.REVENUE.value, 0))
        m_expenses.append(d.get(EntryType.EXPENSE.value, 0))

    return render_template(
        'finance/index.html',
        entries=entries,
        total_revenue=total_revenue,
        total_expense=total_expense,
        balance=balance,
        type_filter=type_filter,
        scope_filter=scope_filter,
        month_filter=month_filter,
        chart_labels=json.dumps(m_labels),
        chart_revenues=json.dumps(m_revenues),
        chart_expenses=json.dumps(m_expenses),
        title=_('Finances'),
    )


@finance_bp.route('/entry/new', methods=['GET', 'POST'])
@technician_required
def create_entry():
    form = FinanceEntryForm()
    if form.validate_on_submit():
        entry = FinanceEntry(
            entry_type=form.entry_type.data,
            category=form.category.data,
            description=form.description.data.strip(),
            amount_xaf=form.amount_xaf.data,
            entry_date=form.entry_date.data,
            production_scope=form.production_scope.data,
            payment_method=form.payment_method.data or None,
            reference_number=form.reference_number.data or None,
            notes=form.notes.data or None,
            recorded_by_id=current_user.id,
        )
        entry.save()
        flash(_('Entrée « %(desc)s » enregistrée.', desc=entry.description), 'success')
        return redirect(url_for('finance.index'))
    form.entry_date.data = form.entry_date.data or date.today()
    return render_template(
        'finance/form.html', form=form,
        title=_('Nouvelle entrée financière'), is_edit=False,
    )


@finance_bp.route('/entry/<entry_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_entry(entry_id):
    entry = FinanceEntry.get_by_id(entry_id) or abort(404)
    form  = FinanceEntryForm(obj=entry)
    if form.validate_on_submit():
        entry.entry_type      = EntryType(form.entry_type.data)
        entry.category        = form.category.data
        entry.description     = form.description.data.strip()
        entry.amount_xaf      = form.amount_xaf.data
        entry.entry_date      = form.entry_date.data
        entry.production_scope = ProductionScope(form.production_scope.data)
        entry.payment_method  = form.payment_method.data or None
        entry.reference_number = form.reference_number.data or None
        entry.notes           = form.notes.data or None
        entry.save()
        flash(_('Entrée mise à jour.'), 'success')
        return redirect(url_for('finance.index'))
    form.entry_type.data      = entry.entry_type.value
    form.production_scope.data = entry.production_scope.value
    return render_template(
        'finance/form.html', form=form, entry=entry,
        title=_('Modifier l\'entrée'), is_edit=True,
    )


@finance_bp.route('/entry/<entry_id>/delete', methods=['POST'])
@technician_required
def delete_entry(entry_id):
    entry = FinanceEntry.get_by_id(entry_id) or abort(404)
    entry.delete()
    flash(_('Entrée supprimée.'), 'success')
    return redirect(url_for('finance.index'))


@finance_bp.route('/summary')
@technician_required
def summary():
    scope_rows    = FinanceEntry.summary_by_scope_and_type()
    category_rows = FinanceEntry.summary_by_category()

    data = {}
    for row in scope_rows:
        scope = row['_id']['scope']
        etype = row['_id']['type']
        if scope not in data:
            data[scope] = {'EXPENSE': 0.0, 'REVENUE': 0.0}
        data[scope][etype] = float(row['total'] or 0)

    # Adapt category_rows to the same namedtuple-style access the template expects
    # Template uses: row.category, row.entry_type, row.total
    from types import SimpleNamespace
    cat_rows = [
        SimpleNamespace(
            category=r['_id']['category'],
            entry_type=r['_id']['type'],
            total=r['total'],
        )
        for r in category_rows
    ]

    return render_template(
        'finance/summary.html',
        data=data,
        category_rows=cat_rows,
        title=_('Résumé financier'),
    )
