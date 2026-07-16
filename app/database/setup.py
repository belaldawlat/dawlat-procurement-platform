from database.connection import get_connection
from database.shipment_schema import create_shipment_tables


def create_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                partner_type TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                whatsapp TEXT,
                website TEXT,
                products_services TEXT,
                status TEXT NOT NULL DEFAULT 'Prospect',
                verification_status TEXT NOT NULL DEFAULT 'Unverified',
                rating INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Admin',
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                sku TEXT NOT NULL UNIQUE,
                unit TEXT NOT NULL,
                country_of_origin TEXT,
                description TEXT,
                specifications TEXT,
                packaging TEXT,
                required_certificates TEXT,
                storage_requirements TEXT,
                status TEXT NOT NULL DEFAULT 'Active'
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                customer_type TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                whatsapp TEXT,
                website TEXT,
                products_of_interest TEXT,
                estimated_demand TEXT,
                preferred_packaging TEXT,
                payment_terms TEXT,
                credit_status TEXT NOT NULL DEFAULT 'Not Assessed',
                lead_status TEXT NOT NULL DEFAULT 'Prospect',
                source TEXT,
                notes TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                product TEXT NOT NULL,
                industry TEXT NOT NULL,
                country TEXT NOT NULL,
                state TEXT,
                city TEXT,
                buyer_company TEXT,
                opportunity_type TEXT NOT NULL DEFAULT 'Import',
                estimated_quantity TEXT,
                target_price TEXT,
                estimated_landed_cost TEXT,
                estimated_sale_price TEXT,
                expected_margin TEXT,
                urgency TEXT NOT NULL DEFAULT 'Medium',
                demand_score INTEGER NOT NULL DEFAULT 50,
                competition_score INTEGER NOT NULL DEFAULT 50,
                confidence_score INTEGER NOT NULL DEFAULT 50,
                status TEXT NOT NULL DEFAULT 'Research',
                source TEXT,
                notes TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rfqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfq_number TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                opportunity_id INTEGER,
                supplier_id INTEGER,
                supplier_name TEXT,
                quantity TEXT NOT NULL,
                unit TEXT NOT NULL,
                specifications TEXT,
                packaging_requirements TEXT,
                certificate_requirements TEXT,
                destination TEXT,
                preferred_incoterm TEXT,
                sample_requirements TEXT,
                payment_requirements TEXT,
                required_documents TEXT,
                response_deadline TEXT,
                status TEXT NOT NULL DEFAULT 'Draft',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS supplier_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfq_id INTEGER NOT NULL,
                supplier_id INTEGER,
                supplier_name TEXT NOT NULL,
                quote_reference TEXT,
                currency TEXT NOT NULL DEFAULT 'USD',
                unit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                freight_cost REAL NOT NULL DEFAULT 0,
                insurance_cost REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,
                incoterm TEXT NOT NULL DEFAULT 'CIF',
                moq TEXT,
                lead_time_days INTEGER NOT NULL DEFAULT 0,
                payment_terms TEXT,
                packaging TEXT,
                certificates TEXT,
                sample_available INTEGER NOT NULL DEFAULT 0,
                sample_cost REAL NOT NULL DEFAULT 0,
                quotation_valid_until TEXT,
                quality_score INTEGER NOT NULL DEFAULT 50,
                compliance_score INTEGER NOT NULL DEFAULT 50,
                communication_score INTEGER NOT NULL DEFAULT 50,
                reliability_score INTEGER NOT NULL DEFAULT 50,
                risk_score INTEGER NOT NULL DEFAULT 50,
                status TEXT NOT NULL DEFAULT 'Received',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS landed_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rfq_id INTEGER,
                supplier_quote_id INTEGER,
                product_name TEXT NOT NULL,
                supplier_name TEXT,
                origin_country TEXT,
                destination TEXT NOT NULL,
                source_currency TEXT NOT NULL,
                reporting_currency TEXT NOT NULL DEFAULT 'AUD',
                exchange_rate REAL NOT NULL DEFAULT 1,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                unit_price_source REAL NOT NULL,
                goods_value_source REAL NOT NULL,
                goods_value_reporting REAL NOT NULL,
                international_freight REAL NOT NULL DEFAULT 0,
                international_insurance REAL NOT NULL DEFAULT 0,
                origin_charges REAL NOT NULL DEFAULT 0,
                destination_port_charges REAL NOT NULL DEFAULT 0,
                customs_broker_fee REAL NOT NULL DEFAULT 0,
                biosecurity_fee REAL NOT NULL DEFAULT 0,
                inspection_fee REAL NOT NULL DEFAULT 0,
                duty_rate REAL NOT NULL DEFAULT 0,
                duty_amount REAL NOT NULL DEFAULT 0,
                gst_rate REAL NOT NULL DEFAULT 10,
                gst_amount REAL NOT NULL DEFAULT 0,
                local_transport REAL NOT NULL DEFAULT 0,
                warehouse_cost REAL NOT NULL DEFAULT 0,
                packaging_cost REAL NOT NULL DEFAULT 0,
                bank_fee REAL NOT NULL DEFAULT 0,
                finance_cost REAL NOT NULL DEFAULT 0,
                contingency REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,
                total_landed_cost REAL NOT NULL DEFAULT 0,
                landed_cost_per_unit REAL NOT NULL DEFAULT 0,
                selling_price_per_unit REAL NOT NULL DEFAULT 0,
                expected_revenue REAL NOT NULL DEFAULT 0,
                gross_profit REAL NOT NULL DEFAULT 0,
                gross_margin_percent REAL NOT NULL DEFAULT 0,
                roi_percent REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Draft',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS logistics_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                rfq_id INTEGER,
                supplier_quote_id INTEGER,
                origin_country TEXT NOT NULL,
                origin_city_port TEXT,
                destination_country TEXT NOT NULL,
                destination_city_port TEXT NOT NULL,
                transport_mode TEXT NOT NULL,
                service_type TEXT NOT NULL,
                container_type TEXT,
                incoterm TEXT,
                cargo_description TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL,
                gross_weight_kg REAL NOT NULL DEFAULT 0,
                volume_cbm REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL,
                freight_cost REAL NOT NULL DEFAULT 0,
                origin_charges REAL NOT NULL DEFAULT 0,
                destination_charges REAL NOT NULL DEFAULT 0,
                customs_clearance_fee REAL NOT NULL DEFAULT 0,
                biosecurity_fee REAL NOT NULL DEFAULT 0,
                inspection_fee REAL NOT NULL DEFAULT 0,
                local_delivery_fee REAL NOT NULL DEFAULT 0,
                warehouse_fee REAL NOT NULL DEFAULT 0,
                insurance_cost REAL NOT NULL DEFAULT 0,
                documentation_fee REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,
                transit_days INTEGER NOT NULL DEFAULT 0,
                validity_date TEXT,
                departure_frequency TEXT,
                route_details TEXT,
                inclusions TEXT,
                exclusions TEXT,
                reliability_score INTEGER NOT NULL DEFAULT 50,
                communication_score INTEGER NOT NULL DEFAULT 50,
                price_score INTEGER NOT NULL DEFAULT 50,
                service_score INTEGER NOT NULL DEFAULT 50,
                risk_score INTEGER NOT NULL DEFAULT 50,
                status TEXT NOT NULL DEFAULT 'Received',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                logistics_quote_id INTEGER,
                rfq_id INTEGER,
                supplier_quote_id INTEGER,
                country TEXT NOT NULL,
                state_region TEXT,
                city TEXT NOT NULL,
                address TEXT,
                warehouse_type TEXT NOT NULL,
                service_model TEXT NOT NULL,
                temperature_controlled INTEGER NOT NULL DEFAULT 0,
                bonded_warehouse INTEGER NOT NULL DEFAULT 0,
                food_grade INTEGER NOT NULL DEFAULT 0,
                product_description TEXT NOT NULL,
                quantity REAL NOT NULL,
                storage_unit TEXT NOT NULL,
                estimated_storage_days INTEGER NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'AUD',
                receiving_fee REAL NOT NULL DEFAULT 0,
                container_unloading_fee REAL NOT NULL DEFAULT 0,
                devanning_fee REAL NOT NULL DEFAULT 0,
                storage_rate REAL NOT NULL DEFAULT 0,
                minimum_monthly_charge REAL NOT NULL DEFAULT 0,
                pallet_in_fee REAL NOT NULL DEFAULT 0,
                pallet_out_fee REAL NOT NULL DEFAULT 0,
                pick_pack_fee REAL NOT NULL DEFAULT 0,
                labelling_fee REAL NOT NULL DEFAULT 0,
                repacking_fee REAL NOT NULL DEFAULT 0,
                cross_docking_fee REAL NOT NULL DEFAULT 0,
                inventory_management_fee REAL NOT NULL DEFAULT 0,
                local_delivery_fee REAL NOT NULL DEFAULT 0,
                disposal_fee REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,
                free_storage_days INTEGER NOT NULL DEFAULT 0,
                minimum_term_months INTEGER NOT NULL DEFAULT 0,
                capacity_description TEXT,
                delivery_zones TEXT,
                operating_hours TEXT,
                systems_integrations TEXT,
                insurance_details TEXT,
                certifications TEXT,
                inclusions TEXT,
                exclusions TEXT,
                price_score INTEGER NOT NULL DEFAULT 50,
                location_score INTEGER NOT NULL DEFAULT 50,
                service_score INTEGER NOT NULL DEFAULT 50,
                capacity_score INTEGER NOT NULL DEFAULT 50,
                technology_score INTEGER NOT NULL DEFAULT 50,
                reliability_score INTEGER NOT NULL DEFAULT 50,
                communication_score INTEGER NOT NULL DEFAULT 50,
                compliance_score INTEGER NOT NULL DEFAULT 50,
                risk_score INTEGER NOT NULL DEFAULT 50,
                status TEXT NOT NULL DEFAULT 'Received',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

    create_shipment_tables()


if __name__ == "__main__":
    create_database()
    print("✅ Database created successfully.")