import random
import psycopg
from datetime import date
from faker import Faker

db_uri = (
    f"host='localhost'"
    f"port='5433'"
    f"dbname='data_management'"
    f"user='postgres'"
    f"password='password'"
)

generate = Faker('id_ID')
Faker.seed(42)
random.seed(42)

def backfill_partner(c):
    partners = [
        ('PT PLN (Persero)', 'biller', 'electricity'),
        ('Perumda Air Minum Kota', 'biller', 'water'),
        ('BPJS Kesehatan', 'biller', 'insurance'),
        ('PT Taspen (Persero)', 'fund_distributor', 'pension'),
        ('Kementerian Sosial RI', 'fund_distributor', 'social_welfare')
    ]

    c.executemany(
        "INSERT INTO Partner (partner_name, partner_type, sector) VALUES (%s, %s, %s)",
        partners,
    )

def backfill_fund_distribution_programs(c):
    c.execute("SELECT sector, partner_id FROM Partner WHERE partner_type = 'fund_distributor'")
    distributor_ids = dict(c.fetchall())

    start_date, end_date = date(2026, 10, 1), date(2026, 10, 31)
    programs = [
        ('Pembayaran Pensiun', 'pension', start_date, end_date, 2_000_000_000_000, 'active', distributor_ids['pension']),
        ('Bansos', 'social_assistance', start_date, end_date, 1_000_000_000, 'active', distributor_ids['social_welfare'])
    ]

    c.executemany(
        "INSERT INTO Fund_Distribution_Program (program_name, program_type, start_date, end_date, total_budget, program_status, partner_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        programs
    )

def backfill_customers(c):
    registration_start, registration_end = date(2020, 1, 1), date (2026, 6, 1)
    customers = []

    for _ in range(9_900):
        type_id = random.choices(['identity_card', 'passport'], weights = [95, 5])[0]
        if type_id == "identity_card":
            id_no = generate.unique.numerify('%###############')
        else:
            id_no = generate.unique.numerify('X#######')

        customers.append((
            'individual',
            generate.name(),
            generate.city(),
            type_id,
            id_no,
            random.choices(['verified', 'pending', 'rejected'], weights=[85, 10, 5])[0],
            random.choices(['active', 'blocked', 'closed'], weights=[90, 5, 5])[0],
            generate.date_between(registration_start, registration_end),
        ))

    for _ in range(100):
        customers.append((
            'organization',
            generate.company(),
            generate.city(),
            'business_registration',
            generate.unique.numerify('%############'),  # dummy NIB, 13 digit
            random.choices(['verified', 'pending', 'rejected'], weights=[85, 10, 5])[0],
            random.choices(['active', 'blocked', 'closed'], weights=[90, 5, 5])[0],
            generate.date_between(registration_start, registration_end),
        ))

    c.executemany(
        "INSERT INTO Customer (customer_type, customer_name, city, id_type, id_no, kyc_status, customer_status, registered_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        customers,
    )

def backfill_accounts(c):
    c.execute(
        "SELECT customer_id, customer_name, customer_status, registered_date FROM Customer WHERE kyc_status = 'verified'"
    )

    accounts = []

    for customer_id, customer_name, customer_status, registered_date in c.fetchall():
        if customer_status == 'closed':
            account_status = 'closed'
        else:
            account_status = random.choices(['active', 'dormant', 'closed'], weights=[85, 10, 5])[0]

        accounts.append((
            generate.unique.numerify('%##########'),
            customer_name,
            registered_date,
            account_status,
            0 if account_status == 'closed' else random.randint(0, 3_000_000) * 1_000,
            customer_id
        ))

    c.executemany(
        "INSERT INTO Account (account_no, account_name, opened_date, account_status, current_balance, customer_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        accounts,
    )

def backfill_bills(c):
    c.execute("SELECT sector, partner_id FROM Partner WHERE partner_type = 'biller'")
    biller_ids = dict(c.fetchall())

    ### digit buat customer number yang nanti di generate random
    subscribers = {
        'electricity': (2_000, '%###########'),   # 12 digit
        'water': (1_000, '%#######'),              # 8 digit
        'insurance': (1_000, '%############'),     # 13 digit
    }

    periods = [date(2026, month, 1) for month in range(1, 11)]
    bills = []

    for sector, (total, number_format) in subscribers.items():
        for _ in range(total):
            biller_customer_no = generate.unique.numerify(number_format)

            if sector == 'electricity':
                amount = random.randint(100, 1_500) * 1_000 # Tagihan PLN antara 100 ribu sampai 1.5 juta
            elif sector == 'water':
                amount = random.randint(50, 400) * 1_000 # Tagihan air antara 50 ribu sampai 400 ribu
            else:
                amount = random.choice([100_000, 150_000]) * random.randint(1, 5) # Tagihan BPJS antara 100 dan 150 ribu dikali jumlah orang antara 1 sampai 5

            for period in periods:
                bills.append((
                    biller_customer_no,
                    period,
                    amount,
                    period.replace(day=20),
                    biller_ids[sector],
                ))

    c.executemany(
        "INSERT INTO Bill (biller_customer_no, billing_period, bill_amount, due_date, partner_id) VALUES (%s, %s, %s, %s, %s)",
        bills,
    )

def backfill_account_transactions(c):
    c.execute("SELECT account_id, customer_id, opened_date, current_balance FROM Account WHERE account_status = 'active'")

    transactions = []
    account_transactions = []
    balances = []

    for account_id, customer_id, opened_date, balance in c.fetchall():
        movement_types = ['transfer'] * 90 + ['deposit'] * 5 + ['withdrawal'] * 5
        random.shuffle(movement_types)

        # tanggal transaksi antara awal akun dibuka sampai 2026-08-1
        transaction_date = sorted(generate.date_time_between(opened_date, date(2026, 8, 1)) for _ in movement_types)

        for movement_type, transaction_datetime in zip(movement_types, transaction_date):
            if movement_type == 'deposit':
                amount = random.randint(1, 50) * 100_000  # amount antara 100 ribu sampai 5 juta
            else:
                amount = random.randint(1, 100) * 10_000  # 10 ribu sampai 1 juta

            # kalo amount yang lebih dari balance kita anggap deposit, biar ga ke track as transfer
            if movement_type != 'deposit' and amount > balance:
                movement_type = 'deposit'

            balance_before = balance
            balance = balance + amount if movement_types == 'deposit' else balance - amount
            reference_no = generate.unique.numerify('TRX-#########')
            counterparty_account_no = generate.numerify('%#########') if movement_type == 'transfer' else None

            transactions.append(('account', transaction_datetime, amount, reference_no, balance_before, balance, customer_id, account_id))
            account_transactions.append((reference_no, movement_type, counterparty_account_no))

        balances.append((balance, account_id))

    query_transaction = "COPY Transaction (transaction_type, transaction_datetime, amount, reference_no, balance_before, balance_after, customer_id, account_id) FROM STDIN"
    with c.copy(query_transaction) as copy:
        for row in transactions:
            copy.write_row(row)

    # ambil transaction_id hasil generate DB, mapping lewat reference_no
    c.execute("SELECT reference_no, transaction_id FROM Transaction WHERE transaction_type = 'account'")
    transaction_ids = dict(c.fetchall())

    with c.copy("COPY Account_Transaction (transaction_id, movement_type, counterparty_account_no) FROM STDIN") as copy:
        for reference_no, movement_type, counterparty_account_no in account_transactions:
            copy.write_row((transaction_ids[reference_no], movement_type, counterparty_account_no))

    c.executemany(
        "UPDATE Account SET current_balance = %s WHERE account_id = %s",
        balances,
    )

def backfill_bill_payments(c):
    c.execute("SELECT customer_id FROM Customer WHERE customer_status = 'active' AND registered_date < '2026-01-01'")
    customer_ids = [row[0] for row in c.fetchall()]

    c.execute("SELECT bill_id, biller_customer_no, billing_period, bill_amount, due_date FROM Bill")

    owners = {}
    transactions = []
    bill_payments = []

    for bill_id, biller_customer_no, billing_period, bill_amount, due_date in c.fetchall():
        if random.random() < 0.1: # simulasi bahwa 10% tagihan tidak dibayar
            continue

        customer_id = owners.setdefault(biller_customer_no, random.choice(customer_ids)) # satu pelanggan biller selalu dibayar customer yang sama
        transaction_datetime = generate.date_time_between(billing_period, billing_period.replace(day=25))
        penalty_amount = 5_000 if transaction_datetime.date() > due_date else 0
        reference_no = generate.unique.numerify('BILL-############')

        transactions.append(('bill_payment', transaction_datetime, bill_amount + penalty_amount, reference_no, customer_id))
        bill_payments.append((
            reference_no,
            random.choices(['cash', 'electronic_money', 'giro', 'other'], weights=[60, 30, 5, 5])[0],
            generate.numerify('%###############'),  # buat reference number
            transaction_datetime,
            bill_id,
        ))

    with c.copy("COPY Transaction (transaction_type, transaction_datetime, amount, reference_no, customer_id) FROM STDIN") as copy:
        for row in transactions:
            copy.write_row(row)

    c.execute("SELECT reference_no, transaction_id FROM Transaction WHERE transaction_type = 'bill_payment'")
    transaction_ids = dict(c.fetchall())

    with c.copy("COPY Bill_Payment (transaction_id, payment_method, biller_reference_no, confirmed_datetime, bill_id) FROM STDIN") as copy:
        for reference_no, *bill_payment in bill_payments:
            copy.write_row((transaction_ids[reference_no], *bill_payment))

    c.execute(
        "UPDATE Bill b SET bill_status = 'paid', penalty_amount = t.amount - b.bill_amount "
        "FROM Bill_Payment bp JOIN Transaction t USING (transaction_id) "
        "WHERE bp.bill_id = b.bill_id"
    )

with psycopg.connect(db_uri) as conn:
    with conn.cursor() as c:
        # BACKFILL PARTNER
        backfill_partner(c)

        # BACKFILL FUND DISTRIBUTION PROGRAM
        backfill_fund_distribution_programs(c)

        # BACKFILL CUSTOMER
        backfill_customers(c)

        # BACKFILL ACCOUNT
        backfill_accounts(c)

        # BACKFILL BILL
        backfill_bills(c)

        # BACKFILL ACCOUNT TRANSACTION
        backfill_account_transactions(c)

        # BACKFILL BILL PAYMENT
        backfill_bill_payments(c)

