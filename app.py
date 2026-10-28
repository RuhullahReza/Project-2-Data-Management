import random
import psycopg
from datetime import date, timedelta
from faker import Faker
from pathlib import Path

db_uri = "host=localhost port=5433 dbname=data_management user=postgres password=password"

generate = Faker('id_ID')
Faker.seed(42)
random.seed(42)

def create_tables(c):
    c.execute(Path(__file__).with_name('DDL.sql').read_text())

    print("selesai create table")

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

    print("selesai backfill partner")

def backfill_fund_distribution_programs(c):
    c.execute("SELECT sector, partner_id FROM Partner WHERE partner_type = 'fund_distributor'")
    distributor_ids = dict(c.fetchall())

    start_date, end_date = date(2026, 9, 1), date(2026, 10, 1)
    programs = [
        ('Pembayaran Pensiun', 'pension', start_date, end_date, 2_000_000_000_000, 'active', distributor_ids['pension']),
        ('Bansos', 'social_assistance', start_date, end_date, 1_000_000_000, 'active', distributor_ids['social_welfare'])
    ]

    c.executemany(
        """
        INSERT INTO Fund_Distribution_Program (program_name, program_type, start_date, end_date, total_budget, program_status, partner_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        programs
    )

    print("selesai backfill fund distribution program")

def backfill_customers(c):
    registration_start, registration_end = date(2020, 1, 1), date (2026, 6, 1)
    customers = []

    for _ in range(9_900):
        # misal 95 % pakai ktp sisanya pakai passport
        type_id = random.choices(['identity_card', 'passport'], weights = [95, 5])[0]
        if type_id == "identity_card":
            id_no = generate.unique.numerify('%###############')
        else:
            id_no = generate.unique.numerify('X#######')

        customers.append((
            'individual', # customer_type
            generate.name(), # customer_name
            generate.city(), # city
            type_id, # id_type
            id_no, # id_no, nomor ktp atau passport
            random.choices(['verified', 'pending', 'rejected'], weights=[85, 10, 5])[0], # kyc_status dibagi 85% verified 10% pending sisanya rejected
            random.choices(['active', 'blocked', 'closed'], weights=[90, 5, 5])[0], # customer_status 90% aktif, 5% blocked 5% closed
            generate.date_between(registration_start, registration_end), # registered_date
        ))

    for _ in range(100):
        customers.append((
            'organization', # customer_type
            generate.company(), # customer_name
            generate.city(), # city
            'business_registration',
            generate.unique.numerify('%############'), # id_no, NIB 13 digit
            random.choices(['verified', 'pending', 'rejected'], weights=[85, 10, 5])[0], # kyc_status dibagi 85% verified 10% pending sisanya rejected
            random.choices(['active', 'blocked', 'closed'], weights=[90, 5, 5])[0], # customer_status 90% aktif, 5% blocked 5% closed
            generate.date_between(registration_start, registration_end), # registered_date
        ))

    c.executemany(
        "INSERT INTO Customer (customer_type, customer_name, city, id_type, id_no, kyc_status, customer_status, registered_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        customers,
    )

    print(f"selesai backfill customer sebanyak {len(customers)} data")

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
            generate.unique.numerify('%##########'), # account_no
            customer_name, # account_name, dibuat sama kaya customer
            registered_date, # opened_date, dibuat sama kaya tanggal daftar si customer
            account_status, # account status
            0 if account_status == 'closed' else random.randint(0, 3_000_000) * 1_000, #current_balance, antara 0 - 3 miliar
            customer_id
        ))

    c.executemany(
        "INSERT INTO Account (account_no, account_name, opened_date, account_status, current_balance, customer_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        accounts,
    )

    print(f"selesai backfill account sebanyak {len(accounts)} data")

def backfill_bills(c):
    c.execute("SELECT sector, partner_id FROM Partner WHERE partner_type = 'biller'")
    biller_ids = dict(c.fetchall())

    ### digit buat customer number yang nanti di generate random
    subscribers = {
        'electricity': (2_000, '%###########'),   # 12 digit
        'water': (1_000, '%#######'),             # 8 digit
        'insurance': (1_000, '%############'),    # 13 digit
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
                    biller_customer_no, # biller_customer_no
                    period, # billing_period
                    amount, # bill_amount
                    period.replace(day=20), # due_date, tanggal 20 di bulan tagihan
                    biller_ids[sector], # partner_id
                ))

    c.executemany(
        "INSERT INTO Bill (biller_customer_no, billing_period, bill_amount, due_date, partner_id) VALUES (%s, %s, %s, %s, %s)",
        bills,
    )

    print(f"selesai backfill bill sebanyak {len(bills)} data")

def backfill_account_transactions(c):
    c.execute("SELECT account_id, customer_id, opened_date, current_balance FROM Account WHERE account_status = 'active'")

    transactions = []
    account_transactions = []
    balances = []

    for account_id, customer_id, opened_date, balance in c.fetchall():
        movement_types = ['transfer'] * 90 + ['deposit'] * 5 + ['withdrawal'] * 5 # dari 100 transaksi 90 transfer 5 deposit 5 withdrawal
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
            balance = balance + amount if movement_type == 'deposit' else balance - amount
            reference_no = generate.unique.numerify('TRX-#########')
            counterparty_account_no = generate.numerify('%#########') if movement_type == 'transfer' else None

            transactions.append((
                'account', # transaction_type
                transaction_datetime,
                amount,
                reference_no,
                balance_before, 
                balance, # balance_after
                customer_id, 
                account_id
            ))
            
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

    print(f"selesai backfill account_transaction sebanyak {len(account_transactions)} data")

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

        transactions.append((
            'bill_payment', # transaction_type
            transaction_datetime, 
            bill_amount + penalty_amount, # amount = tagihan + denda
            reference_no, 
            customer_id
        ))

        bill_payments.append((
            reference_no,
            random.choices(['cash', 'electronic_money', 'giro', 'other'], weights=[60, 30, 5, 5])[0], # random dimana cash 60% electronic money 30% sisanya 5 % 5 %
            generate.numerify('%###############'), # biller_reference_no
            transaction_datetime, # confirmed_datetime
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

    print(f"selesai backfill bill_payment sebanyak {len(bill_payments)} data")

def backfill_remittances(c):
    c.execute("SELECT customer_id FROM Customer WHERE customer_status = 'active' AND registered_date < '2026-01-01'")
    customer_ids = [row[0] for row in c.fetchall()]

    transactions = []
    remittances = []
    money_orders = []
    phones = []

    for _ in range(20_000): 
        transaction_datetime = generate.date_time_between(date(2026, 1, 1), date(2026, 8, 1))
        amount = random.randint(1, 100) * 100_000  # amount antara 100 ribu sampai 10 juta
        reference_no = generate.unique.numerify('RMT-############') 

        if random.random() < 0.85:
            service_scope, country_code = 'domestic', 'ID'
            delivery_method = random.choices(['cash_pickup', 'bank_account'], weights=[60, 40])[0]
        else:
            service_scope, country_code = 'international', random.choice(['MY', 'SG', 'SA', 'HK', 'TW'])
            delivery_method = 'bank_account'

        transactions.append((
            'remittance', # transaction_type
            transaction_datetime,
            amount, 
            reference_no, 
            random.choice(customer_ids) # customer_id pengirim
        ))

        remittances.append((
            reference_no,
            service_scope,
            country_code,
            delivery_method,
            random.choice(['Kiriman Keluarga', 'Biaya Pendidikan', 'Modal Usaha', None]) # purpose
        ))

        # money order hanya untuk kiriman tunai yang diambil di loket
        if delivery_method == 'cash_pickup':
            collection_code = generate.unique.numerify("MO-##########")

            # expiry date nya setelah 30 hari dari transactiond date
            expiry_date = transaction_datetime.date() + timedelta(days=30)

            if random.random() < 0.85:
                order_status = 'cashed'
            elif expiry_date < date(2026, 8, 1):
                order_status = 'expired'
            else:
                order_status = 'issued'

            money_orders.append((
                reference_no, 
                collection_code, 
                generate.name(), # receiver_name
                amount, # order_amount, ngikut angka remittance
                expiry_date, 
                order_status
            ))

            phones.append((collection_code, generate.numerify('08##########')))

            # 30% penerima ada nomor kedua   
            if random.random() < 0.3:
                 phones.append((collection_code, generate.numerify('08##########')))

    with c.copy("COPY Transaction (transaction_type, transaction_datetime, amount, reference_no, customer_id) FROM STDIN") as copy:
        for row in transactions:
            copy.write_row(row)

    c.execute("SELECT reference_no, transaction_id FROM Transaction WHERE transaction_type = 'remittance'")
    transaction_ids = dict(c.fetchall())

    with c.copy("COPY Remittance (transaction_id, service_scope, destination_country_code, delivery_method, purpose) FROM STDIN") as copy:
        for reference_no, *remittance in remittances:
            copy.write_row((transaction_ids[reference_no], *remittance))
    
    with c.copy("COPY Money_Order (transaction_id, collection_code, receiver_name, order_amount, expiry_date, order_status) FROM STDIN") as copy:
        for reference_no, *money_order in money_orders:
            copy.write_row((transaction_ids[reference_no], *money_order))

    c.execute("SELECT collection_code, money_order_id FROM Money_Order")
    money_order_ids = dict(c.fetchall())

    with c.copy("COPY Money_Order_Receiver_Phone (money_order_id, receiver_phone) FROM STDIN") as copy:
        for collection_code, receiver_phone in phones:
            copy.write_row((money_order_ids[collection_code], receiver_phone))

    print(f"selesai backfill remittance sebanyak {len(remittances)} data")
 
def backfill_disbursements(c):
    transactions = []
    disbursements = []
    payouts = []

    c.execute(
        """
        SELECT m.money_order_id, m.receiver_name, m.order_amount, m.expiry_date, t.transaction_datetime
        FROM Money_Order m JOIN Transaction t USING (transaction_id) WHERE m.order_status = 'cashed'
        """
    )

    for money_order_id, receiver_name, order_amount, expiry_date, remittance_datetime in c.fetchall():
        # tanggal payout setelah remittance dan sebelum expired
        payout_datetime = generate.date_time_between(remittance_datetime, min(expiry_date, date(2026, 8, 1)))
        reference_no = generate.unique.numerify('DIS-############')

        transactions.append((
            'disbursement', # transaction_type
            payout_datetime, 
            order_amount, 
            reference_no, 
            None # customer_id, pengirim
        ))
        
        disbursements.append((
            reference_no, 
            'cash', # disbursement_method
            'collection_code', # verification_method
            None # verified_id_no
        ))

        payouts.append((
            reference_no, 
            receiver_name, 
            None, # receiver_id_no
            order_amount,
            payout_datetime, 
            money_order_id,
            None # program_id
        ))

    c.execute("SELECT program_type, program_id FROM Fund_Distribution_Program")
    program_ids = dict(c.fetchall())

    c.execute(
        """
        SELECT customer_id, customer_name, id_no FROM Customer
        WHERE customer_type = 'individual' AND id_type = 'identity_card' AND kyc_status = 'verified' AND customer_status = 'active'
        LIMIT 3000
        """
    )

    for i, (customer_id, customer_name, id_no) in enumerate(c.fetchall()):
        if i < 2_000:
            program_type, amount = 'pension', random.randint(20,50) * 100_000 # antara 2 sampai 5 juta
        else:
            program_type, amount = 'social_assistance', 600_000

        payout_datetime = generate.date_time_between(date(2026, 9, 1), date(2026, 10, 1))
        reference_no = generate.unique.numerify('DIS-############')

        transactions.append((
            'disbursement', # transaction_type
            payout_datetime,
            amount, 
            reference_no, 
            customer_id # customer_id penerima
        ))

        disbursements.append((
            reference_no, 
            'cash', # disbursement_method
            random.choices(['identity_card', 'biometric'], weights=[80, 20])[0],  # verification_method 80% pakai ktp sisanya biometric
            id_no # verified_id_no
        ))

        payouts.append((
            reference_no, 
            customer_name, 
            id_no, 
            amount, 
            payout_datetime, 
            None, # money_order_id
            program_ids[program_type]
        ))

    with c.copy("COPY Transaction (transaction_type, transaction_datetime, amount, reference_no, customer_id) FROM STDIN") as copy:
        for row in transactions:
            copy.write_row(row)

    c.execute("SELECT reference_no, transaction_id FROM Transaction WHERE transaction_type = 'disbursement'")
    transaction_ids = dict(c.fetchall())

    with c.copy("COPY Disbursement (transaction_id, disbursement_method, verification_method, verified_id_no) FROM STDIN") as copy:
        for reference_no, *disbursement in disbursements:
            copy.write_row((transaction_ids[reference_no], *disbursement))

    with c.copy("COPY Payout (transaction_id, receiver_name, receiver_id_no, payout_amount, payout_datetime, money_order_id, program_id) FROM STDIN") as copy:
        for reference_no, *payout in payouts:
            copy.write_row((transaction_ids[reference_no], *payout))
    
    print(f"selesai backfill disbursements sebanyak {len(disbursements)} data")

def backfill_reversals(c):
    c.execute(
        """
        SELECT bp.transaction_id, t.amount, t.transaction_datetime
        FROM Bill_Payment bp JOIN Transaction t using (transaction_id) ORDER BY bp.transaction_id
        """
    )

    reversals = []

    for transaction_id, amount, transaction_datetime in c.fetchall():
        if random.random() >= 0.02: # 2% dari bill payment akan masuk reversal
            continue

        reversals.append((
            transaction_datetime + timedelta(hours=random.randint(1,24)), # reversal_datetime, 1-24 jam setelah bayar
            random.choice(['timeout', 'wrong_input', 'duplicate', 'other']), # reason_code
            amount, # reversed_amount
            random.choices(['completed', 'rejected', 'requested'], weights=[80, 15, 5])[0], # reversal_status 80% completed 15% rejected sisanya requested
            transaction_id
        ))

    c.executemany(
        """
        INSERT INTO Reversal (reversal_datetime, reason_code, reversed_amount, reversal_status, transaction_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        reversals
    )

    c.execute(
        """
        UPDATE bill b SET bill_status = 'unpaid', penalty_amount = 0
        FROM Bill_payment bp JOIN Reversal r USING (transaction_id)
        WHERE bp.bill_id = b.bill_id AND r.reversal_status = 'completed'
        """
    )

    print(f"selesai backfill reversal sebanyak {len(reversals)} data")

def backfill_status_histories(c):
    # status awal transaksi initiated
    c.execute(
        """
        INSERT INTO Status_History (transaction_id, sequence_no, status, status_datetime)
        SELECT transaction_id, 1, 'initiated', transaction_datetime 
        FROM Transaction
        """
    )

    # kasih jarak 5 detik buat berubah jadi success
    c.execute(
        """
        INSERT INTO Status_History (transaction_id, sequence_no, status, status_datetime)
        SELECT transaction_id, 2, 'success', transaction_datetime + interval '5 seconds' 
        FROM Transaction
        """
    )

    # kalo reversal sudah komplit statusnya jadi reversed
    c.execute(
        """
        INSERT INTO Status_History (transaction_id, sequence_no, status, status_datetime, reason_code)
        SELECT transaction_id, 3, 'reversed', reversal_datetime, reason_code 
        FROM Reversal WHERE reversal_status = 'completed'
        """
    )

    print(f"selesai backfill status histories")

def backfill_transaction_fees(c):
    c.execute(
        """
        INSERT INTO Transaction_Fee (transaction_id, fee_no, fee_type, fee_amount, charged_to)
        SELECT transaction_id, 1, 'admin', 2500, 'customer' 
        FROM Transaction
        WHERE transaction_type IN ('bill_payment', 'remittance')
        """
    )

    print(f"selesai backfill transaction fees")

def backfill_receipts(c):
    c.execute(
        """
        INSERT INTO Receipt (issued_datetime, delivery_format, transaction_id)
        SELECT transaction_datetime + interval '5 seconds',
        CASE WHEN transaction_type = 'account' THEN 'digital' ELSE 'printed' END,
        transaction_id 
        FROM Transaction
        """
    )

    print(f"selesai backfill receipts")

with psycopg.connect(db_uri) as conn:
    with conn.cursor() as c:
        # CREATE TABLE
        create_tables(c)

        # biar ga ke backfill lagi kalo udah pernah backfill
        c.execute("SELECT count(*) FROM Customer")
        if c.fetchone()[0] > 0:
            raise SystemExit("sudah pernah backfill")

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

        # BACKFILL REMITTANCE
        backfill_remittances(c)

        # BACKFILL DISBURSEMENT
        backfill_disbursements(c)

        # BACKFILL REVERSAL
        backfill_reversals(c)

        # BACKFILL STATUS HISTORY
        backfill_status_histories(c)

        # BACKFILL TRANSACTION FEE
        backfill_transaction_fees(c)

        # BACKFILL RECEIPT
        backfill_receipts(c)
