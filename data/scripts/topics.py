"""
Topic library for synthetic conversation generation.

Organized by domain with ~1000 topics total. Each topic includes:
- id: unique identifier
- domain: category (retail, banking, healthcare, etc.)
- description: what the conversation is about
- typical_pii: list of PII categories commonly involved in this topic
"""

from dataclasses import dataclass
from enum import Enum
from typing import List
import random


class Domain(str, Enum):
    RETAIL = "retail"
    BANKING = "banking"
    HEALTHCARE = "healthcare"
    TECH_SUPPORT = "tech_support"
    TRAVEL = "travel"
    TELECOM = "telecom"
    UTILITIES = "utilities"
    GENERAL = "general"
    INSURANCE = "insurance"
    GOVERNMENT = "government"


class PIICategory(str, Enum):
    PERSON = "person"
    CONTACT = "contact"
    GOV_ID = "gov_id"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"
    MEDICAL = "medical"
    LOCATION = "location"
    IDENTIFIER = "identifier"


@dataclass
class Topic:
    id: str
    domain: Domain
    description: str
    typical_pii: List[PIICategory]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain.value,
            "description": self.description,
            "typical_pii": [p.value for p in self.typical_pii],
        }


# =============================================================================
# RETAIL / E-COMMERCE (~200 topics)
# =============================================================================

RETAIL_TOPICS = [
    # Order Issues
    Topic("retail_order_status", Domain.RETAIL, "Customer asking about order status or delivery timeline", [PIICategory.IDENTIFIER]),
    Topic("retail_order_tracking", Domain.RETAIL, "Customer needs tracking number or tracking update", [PIICategory.IDENTIFIER]),
    Topic("retail_order_missing", Domain.RETAIL, "Order marked delivered but customer didn't receive it", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("retail_order_damaged", Domain.RETAIL, "Customer received damaged or broken item", [PIICategory.IDENTIFIER]),
    Topic("retail_order_wrong_item", Domain.RETAIL, "Customer received wrong item in their order", [PIICategory.IDENTIFIER]),
    Topic("retail_order_incomplete", Domain.RETAIL, "Order arrived with missing items", [PIICategory.IDENTIFIER]),
    Topic("retail_order_cancel", Domain.RETAIL, "Customer wants to cancel an order before shipping", [PIICategory.IDENTIFIER]),
    Topic("retail_order_modify", Domain.RETAIL, "Customer wants to change items or quantity in order", [PIICategory.IDENTIFIER]),
    Topic("retail_order_expedite", Domain.RETAIL, "Customer wants to upgrade shipping speed", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("retail_order_delay", Domain.RETAIL, "Order is delayed and customer wants update", [PIICategory.IDENTIFIER]),

    # Returns and Refunds
    Topic("retail_return_wrong_size", Domain.RETAIL, "Customer wants to return item due to wrong size", [PIICategory.IDENTIFIER]),
    Topic("retail_return_defective", Domain.RETAIL, "Customer returning defective or malfunctioning item", [PIICategory.IDENTIFIER]),
    Topic("retail_return_changed_mind", Domain.RETAIL, "Customer returning item they no longer want", [PIICategory.IDENTIFIER]),
    Topic("retail_return_not_as_described", Domain.RETAIL, "Item doesn't match product description", [PIICategory.IDENTIFIER]),
    Topic("retail_return_status", Domain.RETAIL, "Customer checking status of return they initiated", [PIICategory.IDENTIFIER]),
    Topic("retail_return_label", Domain.RETAIL, "Customer needs return shipping label", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("retail_refund_status", Domain.RETAIL, "Customer checking when refund will be processed", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("retail_refund_missing", Domain.RETAIL, "Return received but refund not issued yet", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("retail_refund_wrong_amount", Domain.RETAIL, "Refund amount is incorrect", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("retail_exchange", Domain.RETAIL, "Customer wants to exchange item for different size/color", [PIICategory.IDENTIFIER]),

    # Shipping and Delivery
    Topic("retail_shipping_address_change", Domain.RETAIL, "Customer needs to update shipping address", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("retail_shipping_options", Domain.RETAIL, "Customer asking about available shipping methods", []),
    Topic("retail_shipping_international", Domain.RETAIL, "Questions about international shipping", [PIICategory.LOCATION]),
    Topic("retail_delivery_instructions", Domain.RETAIL, "Customer adding special delivery instructions", [PIICategory.LOCATION]),
    Topic("retail_delivery_reschedule", Domain.RETAIL, "Customer needs to reschedule delivery", [PIICategory.IDENTIFIER]),
    Topic("retail_pickup_store", Domain.RETAIL, "Customer wants to pick up order in store", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("retail_shipping_cost", Domain.RETAIL, "Customer asking about shipping costs", []),
    Topic("retail_free_shipping", Domain.RETAIL, "Customer asking about free shipping eligibility", []),

    # Account and Profile
    Topic("retail_account_create", Domain.RETAIL, "Customer creating new account", [PIICategory.CONTACT, PIICategory.PERSON]),
    Topic("retail_account_update_email", Domain.RETAIL, "Customer updating email address on account", [PIICategory.CONTACT]),
    Topic("retail_account_update_phone", Domain.RETAIL, "Customer updating phone number on account", [PIICategory.CONTACT]),
    Topic("retail_account_update_address", Domain.RETAIL, "Customer updating mailing address", [PIICategory.LOCATION]),
    Topic("retail_account_delete", Domain.RETAIL, "Customer wants to delete their account", [PIICategory.CONTACT]),
    Topic("retail_account_locked", Domain.RETAIL, "Customer account is locked or suspended", [PIICategory.CONTACT]),
    Topic("retail_password_reset", Domain.RETAIL, "Customer forgot password and needs reset", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("retail_account_merge", Domain.RETAIL, "Customer wants to merge duplicate accounts", [PIICategory.CONTACT]),

    # Payment and Billing
    Topic("retail_payment_failed", Domain.RETAIL, "Payment was declined or failed", [PIICategory.FINANCIAL]),
    Topic("retail_payment_method_add", Domain.RETAIL, "Customer adding new payment method", [PIICategory.FINANCIAL]),
    Topic("retail_payment_method_update", Domain.RETAIL, "Customer updating payment card on file", [PIICategory.FINANCIAL]),
    Topic("retail_payment_method_remove", Domain.RETAIL, "Customer removing saved payment method", [PIICategory.FINANCIAL]),
    Topic("retail_billing_address", Domain.RETAIL, "Customer updating billing address", [PIICategory.LOCATION]),
    Topic("retail_charge_dispute", Domain.RETAIL, "Customer disputing a charge on their card", [PIICategory.FINANCIAL, PIICategory.IDENTIFIER]),
    Topic("retail_double_charge", Domain.RETAIL, "Customer was charged twice for same order", [PIICategory.FINANCIAL, PIICategory.IDENTIFIER]),
    Topic("retail_promo_code", Domain.RETAIL, "Customer has issue with promo code or discount", [PIICategory.IDENTIFIER]),
    Topic("retail_gift_card_balance", Domain.RETAIL, "Customer checking gift card balance", [PIICategory.IDENTIFIER]),
    Topic("retail_gift_card_issue", Domain.RETAIL, "Gift card not working or has wrong balance", [PIICategory.IDENTIFIER]),

    # Loyalty and Rewards
    Topic("retail_loyalty_enroll", Domain.RETAIL, "Customer signing up for loyalty program", [PIICategory.CONTACT, PIICategory.PERSON]),
    Topic("retail_loyalty_points", Domain.RETAIL, "Customer asking about points balance", [PIICategory.IDENTIFIER]),
    Topic("retail_loyalty_redeem", Domain.RETAIL, "Customer wants to redeem points or rewards", [PIICategory.IDENTIFIER]),
    Topic("retail_loyalty_missing_points", Domain.RETAIL, "Points from purchase not credited", [PIICategory.IDENTIFIER]),
    Topic("retail_loyalty_tier_status", Domain.RETAIL, "Customer asking about membership tier", [PIICategory.IDENTIFIER]),

    # Product Questions
    Topic("retail_product_availability", Domain.RETAIL, "Customer asking if product is in stock", []),
    Topic("retail_product_restock", Domain.RETAIL, "When will out-of-stock item be available", [PIICategory.CONTACT]),
    Topic("retail_product_specs", Domain.RETAIL, "Customer asking about product specifications", []),
    Topic("retail_product_compatibility", Domain.RETAIL, "Will this product work with what I have", []),
    Topic("retail_product_comparison", Domain.RETAIL, "Customer comparing two products", []),
    Topic("retail_product_recommendation", Domain.RETAIL, "Customer asking for product recommendations", []),
    Topic("retail_product_warranty", Domain.RETAIL, "Questions about product warranty", [PIICategory.IDENTIFIER]),
    Topic("retail_product_registration", Domain.RETAIL, "Customer registering product for warranty", [PIICategory.IDENTIFIER, PIICategory.PERSON]),

    # Store and Policy
    Topic("retail_store_hours", Domain.RETAIL, "Customer asking about store hours", []),
    Topic("retail_store_location", Domain.RETAIL, "Customer looking for store locations", []),
    Topic("retail_return_policy", Domain.RETAIL, "Customer asking about return policy", []),
    Topic("retail_price_match", Domain.RETAIL, "Customer wants to price match competitor", [PIICategory.IDENTIFIER]),
    Topic("retail_rain_check", Domain.RETAIL, "Customer asking about rain check for sale item", []),

    # Subscriptions
    Topic("retail_subscription_start", Domain.RETAIL, "Customer signing up for subscription service", [PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("retail_subscription_cancel", Domain.RETAIL, "Customer canceling subscription", [PIICategory.IDENTIFIER]),
    Topic("retail_subscription_pause", Domain.RETAIL, "Customer pausing subscription temporarily", [PIICategory.IDENTIFIER]),
    Topic("retail_subscription_modify", Domain.RETAIL, "Customer changing subscription frequency or items", [PIICategory.IDENTIFIER]),
    Topic("retail_subscription_billing", Domain.RETAIL, "Questions about subscription billing", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),

    # Complaints
    Topic("retail_complaint_service", Domain.RETAIL, "Customer complaining about customer service", []),
    Topic("retail_complaint_quality", Domain.RETAIL, "Customer complaining about product quality", [PIICategory.IDENTIFIER]),
    Topic("retail_complaint_shipping", Domain.RETAIL, "Customer complaining about shipping issues", [PIICategory.IDENTIFIER]),
    Topic("retail_complaint_store", Domain.RETAIL, "Customer complaining about in-store experience", []),
    Topic("retail_feedback_positive", Domain.RETAIL, "Customer providing positive feedback", []),

    # Special Orders
    Topic("retail_custom_order", Domain.RETAIL, "Customer placing custom or personalized order", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("retail_bulk_order", Domain.RETAIL, "Customer placing large bulk order", [PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("retail_backorder", Domain.RETAIL, "Customer asking about backordered item status", [PIICategory.IDENTIFIER]),
    Topic("retail_preorder", Domain.RETAIL, "Customer asking about preorder status", [PIICategory.IDENTIFIER]),

    # Gift Services
    Topic("retail_gift_wrap", Domain.RETAIL, "Customer requesting gift wrapping", [PIICategory.IDENTIFIER]),
    Topic("retail_gift_message", Domain.RETAIL, "Customer adding gift message to order", [PIICategory.IDENTIFIER]),
    Topic("retail_gift_receipt", Domain.RETAIL, "Customer needs gift receipt", [PIICategory.IDENTIFIER]),
    Topic("retail_gift_registry", Domain.RETAIL, "Customer asking about gift registry", [PIICategory.PERSON]),
]

# =============================================================================
# BANKING / FINANCIAL (~150 topics)
# =============================================================================

BANKING_TOPICS = [
    # Account Information
    Topic("banking_balance_check", Domain.BANKING, "Customer checking account balance", [PIICategory.IDENTIFIER]),
    Topic("banking_transaction_history", Domain.BANKING, "Customer asking about recent transactions", [PIICategory.IDENTIFIER]),
    Topic("banking_statement_request", Domain.BANKING, "Customer requesting account statement", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("banking_account_open", Domain.BANKING, "Customer opening new bank account", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.GOV_ID]),
    Topic("banking_account_close", Domain.BANKING, "Customer closing bank account", [PIICategory.IDENTIFIER]),
    Topic("banking_account_type_change", Domain.BANKING, "Customer upgrading or changing account type", [PIICategory.IDENTIFIER]),
    Topic("banking_account_nickname", Domain.BANKING, "Customer setting nickname for account", [PIICategory.IDENTIFIER]),

    # Cards
    Topic("banking_card_lost", Domain.BANKING, "Customer reporting lost debit/credit card", [PIICategory.FINANCIAL, PIICategory.PERSON]),
    Topic("banking_card_stolen", Domain.BANKING, "Customer reporting stolen card", [PIICategory.FINANCIAL, PIICategory.PERSON]),
    Topic("banking_card_damaged", Domain.BANKING, "Customer needs replacement for damaged card", [PIICategory.FINANCIAL, PIICategory.LOCATION]),
    Topic("banking_card_activate", Domain.BANKING, "Customer activating new card", [PIICategory.FINANCIAL]),
    Topic("banking_card_pin_reset", Domain.BANKING, "Customer needs to reset card PIN", [PIICategory.FINANCIAL, PIICategory.CREDENTIALS]),
    Topic("banking_card_limit", Domain.BANKING, "Customer asking about or changing card limit", [PIICategory.FINANCIAL]),
    Topic("banking_card_block", Domain.BANKING, "Customer temporarily blocking card", [PIICategory.FINANCIAL]),
    Topic("banking_card_unblock", Domain.BANKING, "Customer unblocking previously blocked card", [PIICategory.FINANCIAL]),
    Topic("banking_card_expiring", Domain.BANKING, "Customer asking about expiring card replacement", [PIICategory.FINANCIAL]),

    # Transfers
    Topic("banking_transfer_internal", Domain.BANKING, "Customer transferring between own accounts", [PIICategory.IDENTIFIER]),
    Topic("banking_transfer_external", Domain.BANKING, "Customer transferring to another bank", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_wire_domestic", Domain.BANKING, "Customer sending domestic wire transfer", [PIICategory.FINANCIAL, PIICategory.PERSON]),
    Topic("banking_wire_international", Domain.BANKING, "Customer sending international wire", [PIICategory.FINANCIAL, PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("banking_transfer_failed", Domain.BANKING, "Transfer failed or stuck", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_transfer_recall", Domain.BANKING, "Customer wants to recall/cancel transfer", [PIICategory.IDENTIFIER]),
    Topic("banking_zelle_setup", Domain.BANKING, "Customer setting up Zelle", [PIICategory.CONTACT]),
    Topic("banking_zelle_issue", Domain.BANKING, "Problem with Zelle payment", [PIICategory.CONTACT, PIICategory.FINANCIAL]),

    # Disputes and Fraud
    Topic("banking_fraud_alert", Domain.BANKING, "Customer received fraud alert", [PIICategory.FINANCIAL]),
    Topic("banking_fraud_report", Domain.BANKING, "Customer reporting fraudulent activity", [PIICategory.FINANCIAL, PIICategory.IDENTIFIER]),
    Topic("banking_dispute_charge", Domain.BANKING, "Customer disputing unauthorized charge", [PIICategory.FINANCIAL, PIICategory.IDENTIFIER]),
    Topic("banking_dispute_status", Domain.BANKING, "Customer checking dispute status", [PIICategory.IDENTIFIER]),
    Topic("banking_identity_theft", Domain.BANKING, "Customer reporting identity theft", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("banking_suspicious_activity", Domain.BANKING, "Customer reporting suspicious account activity", [PIICategory.IDENTIFIER]),

    # Payments
    Topic("banking_bill_pay_setup", Domain.BANKING, "Customer setting up bill pay", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_bill_pay_issue", Domain.BANKING, "Bill payment didn't go through", [PIICategory.IDENTIFIER]),
    Topic("banking_autopay_setup", Domain.BANKING, "Customer setting up automatic payments", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_autopay_cancel", Domain.BANKING, "Customer canceling automatic payment", [PIICategory.IDENTIFIER]),
    Topic("banking_payment_schedule", Domain.BANKING, "Customer scheduling future payment", [PIICategory.IDENTIFIER]),

    # Loans and Credit
    Topic("banking_loan_application", Domain.BANKING, "Customer applying for loan", [PIICategory.PERSON, PIICategory.GOV_ID, PIICategory.FINANCIAL]),
    Topic("banking_loan_status", Domain.BANKING, "Customer checking loan application status", [PIICategory.IDENTIFIER]),
    Topic("banking_loan_payment", Domain.BANKING, "Customer making loan payment", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_loan_payoff", Domain.BANKING, "Customer wants loan payoff amount", [PIICategory.IDENTIFIER]),
    Topic("banking_mortgage_inquiry", Domain.BANKING, "Customer asking about mortgage options", [PIICategory.FINANCIAL]),
    Topic("banking_mortgage_payment", Domain.BANKING, "Customer making mortgage payment", [PIICategory.IDENTIFIER]),
    Topic("banking_credit_line", Domain.BANKING, "Customer asking about credit line increase", [PIICategory.IDENTIFIER]),
    Topic("banking_heloc", Domain.BANKING, "Customer asking about home equity line of credit", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),

    # Direct Deposit
    Topic("banking_direct_deposit_setup", Domain.BANKING, "Customer setting up direct deposit", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_direct_deposit_verify", Domain.BANKING, "Customer needs account verification letter", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_direct_deposit_missing", Domain.BANKING, "Direct deposit didn't arrive", [PIICategory.IDENTIFIER]),
    Topic("banking_routing_number", Domain.BANKING, "Customer needs routing number", [PIICategory.FINANCIAL]),

    # Fees
    Topic("banking_fee_inquiry", Domain.BANKING, "Customer asking about fees", []),
    Topic("banking_fee_reversal", Domain.BANKING, "Customer requesting fee reversal", [PIICategory.IDENTIFIER]),
    Topic("banking_overdraft_fee", Domain.BANKING, "Customer disputing overdraft fee", [PIICategory.IDENTIFIER]),
    Topic("banking_maintenance_fee", Domain.BANKING, "Customer asking about monthly fee", [PIICategory.IDENTIFIER]),

    # Online and Mobile Banking
    Topic("banking_online_access", Domain.BANKING, "Customer needs help with online banking", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("banking_mobile_app", Domain.BANKING, "Customer has issue with mobile app", [PIICategory.CONTACT]),
    Topic("banking_username_reset", Domain.BANKING, "Customer forgot online banking username", [PIICategory.CONTACT]),
    Topic("banking_password_reset", Domain.BANKING, "Customer needs to reset online password", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("banking_mfa_issue", Domain.BANKING, "Customer having issues with two-factor auth", [PIICategory.CONTACT]),
    Topic("banking_device_register", Domain.BANKING, "Customer registering new device", [PIICategory.CONTACT]),

    # Checks
    Topic("banking_check_order", Domain.BANKING, "Customer ordering new checks", [PIICategory.LOCATION]),
    Topic("banking_check_deposit", Domain.BANKING, "Customer depositing check", [PIICategory.IDENTIFIER]),
    Topic("banking_check_hold", Domain.BANKING, "Customer asking why check is on hold", [PIICategory.IDENTIFIER]),
    Topic("banking_check_stop_payment", Domain.BANKING, "Customer wants to stop payment on check", [PIICategory.IDENTIFIER]),
    Topic("banking_check_bounced", Domain.BANKING, "Customer's check bounced", [PIICategory.IDENTIFIER]),
    Topic("banking_cashiers_check", Domain.BANKING, "Customer needs cashier's check", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),

    # Safe Deposit
    Topic("banking_safe_deposit_rent", Domain.BANKING, "Customer renting safe deposit box", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("banking_safe_deposit_access", Domain.BANKING, "Customer accessing safe deposit box", [PIICategory.PERSON]),
    Topic("banking_safe_deposit_key", Domain.BANKING, "Customer lost safe deposit box key", [PIICategory.PERSON]),

    # Investment
    Topic("banking_investment_inquiry", Domain.BANKING, "Customer asking about investment options", [PIICategory.IDENTIFIER]),
    Topic("banking_ira_contribution", Domain.BANKING, "Customer making IRA contribution", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_cd_inquiry", Domain.BANKING, "Customer asking about CD rates", []),
    Topic("banking_cd_open", Domain.BANKING, "Customer opening certificate of deposit", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("banking_cd_maturity", Domain.BANKING, "Customer asking about CD maturity", [PIICategory.IDENTIFIER]),
]

# =============================================================================
# HEALTHCARE (~100 topics)
# =============================================================================

HEALTHCARE_TOPICS = [
    # Appointments
    Topic("healthcare_appointment_schedule", Domain.HEALTHCARE, "Patient scheduling new appointment", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("healthcare_appointment_reschedule", Domain.HEALTHCARE, "Patient rescheduling existing appointment", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("healthcare_appointment_cancel", Domain.HEALTHCARE, "Patient canceling appointment", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("healthcare_appointment_confirm", Domain.HEALTHCARE, "Patient confirming upcoming appointment", [PIICategory.PERSON]),
    Topic("healthcare_appointment_reminder", Domain.HEALTHCARE, "Patient asking about appointment reminders", [PIICategory.CONTACT]),
    Topic("healthcare_waitlist", Domain.HEALTHCARE, "Patient asking to be put on waitlist", [PIICategory.PERSON, PIICategory.CONTACT]),

    # Prescriptions
    Topic("healthcare_prescription_refill", Domain.HEALTHCARE, "Patient requesting prescription refill", [PIICategory.PERSON, PIICategory.MEDICAL]),
    Topic("healthcare_prescription_transfer", Domain.HEALTHCARE, "Patient transferring prescription to new pharmacy", [PIICategory.PERSON, PIICategory.MEDICAL, PIICategory.LOCATION]),
    Topic("healthcare_prescription_status", Domain.HEALTHCARE, "Patient checking prescription status", [PIICategory.IDENTIFIER, PIICategory.MEDICAL]),
    Topic("healthcare_prescription_price", Domain.HEALTHCARE, "Patient asking about medication cost", [PIICategory.MEDICAL]),
    Topic("healthcare_prescription_generic", Domain.HEALTHCARE, "Patient asking about generic alternatives", [PIICategory.MEDICAL]),
    Topic("healthcare_prescription_side_effects", Domain.HEALTHCARE, "Patient asking about medication side effects", [PIICategory.MEDICAL]),

    # Insurance
    Topic("healthcare_insurance_verify", Domain.HEALTHCARE, "Verifying patient insurance coverage", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("healthcare_insurance_update", Domain.HEALTHCARE, "Patient updating insurance information", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("healthcare_insurance_coverage", Domain.HEALTHCARE, "Patient asking what's covered", [PIICategory.IDENTIFIER]),
    Topic("healthcare_insurance_preauth", Domain.HEALTHCARE, "Patient asking about prior authorization", [PIICategory.IDENTIFIER, PIICategory.MEDICAL]),
    Topic("healthcare_copay_inquiry", Domain.HEALTHCARE, "Patient asking about copay amount", []),
    Topic("healthcare_deductible_status", Domain.HEALTHCARE, "Patient asking about deductible status", [PIICategory.IDENTIFIER]),

    # Billing
    Topic("healthcare_bill_inquiry", Domain.HEALTHCARE, "Patient asking about medical bill", [PIICategory.IDENTIFIER]),
    Topic("healthcare_bill_payment", Domain.HEALTHCARE, "Patient making payment on bill", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("healthcare_bill_dispute", Domain.HEALTHCARE, "Patient disputing charge on bill", [PIICategory.IDENTIFIER]),
    Topic("healthcare_payment_plan", Domain.HEALTHCARE, "Patient setting up payment plan", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("healthcare_itemized_bill", Domain.HEALTHCARE, "Patient requesting itemized statement", [PIICategory.IDENTIFIER]),
    Topic("healthcare_financial_assistance", Domain.HEALTHCARE, "Patient asking about financial assistance", [PIICategory.PERSON, PIICategory.FINANCIAL]),

    # Medical Records
    Topic("healthcare_records_request", Domain.HEALTHCARE, "Patient requesting medical records", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("healthcare_records_transfer", Domain.HEALTHCARE, "Patient transferring records to new provider", [PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("healthcare_records_access", Domain.HEALTHCARE, "Patient accessing online records portal", [PIICategory.PERSON, PIICategory.CREDENTIALS]),
    Topic("healthcare_records_correction", Domain.HEALTHCARE, "Patient requesting correction to records", [PIICategory.PERSON, PIICategory.MEDICAL]),
    Topic("healthcare_test_results", Domain.HEALTHCARE, "Patient asking about test results", [PIICategory.PERSON, PIICategory.MEDICAL]),
    Topic("healthcare_imaging_results", Domain.HEALTHCARE, "Patient asking about imaging results", [PIICategory.PERSON, PIICategory.MEDICAL]),

    # Referrals
    Topic("healthcare_referral_request", Domain.HEALTHCARE, "Patient needs specialist referral", [PIICategory.PERSON, PIICategory.MEDICAL]),
    Topic("healthcare_referral_status", Domain.HEALTHCARE, "Patient checking referral status", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("healthcare_second_opinion", Domain.HEALTHCARE, "Patient asking about second opinion", [PIICategory.PERSON]),

    # Provider Information
    Topic("healthcare_find_doctor", Domain.HEALTHCARE, "Patient looking for doctor accepting new patients", []),
    Topic("healthcare_provider_hours", Domain.HEALTHCARE, "Patient asking about office hours", []),
    Topic("healthcare_provider_location", Domain.HEALTHCARE, "Patient asking about office locations", []),
    Topic("healthcare_provider_credentials", Domain.HEALTHCARE, "Patient asking about doctor's credentials", []),

    # Patient Portal
    Topic("healthcare_portal_registration", Domain.HEALTHCARE, "Patient registering for patient portal", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("healthcare_portal_access", Domain.HEALTHCARE, "Patient having trouble accessing portal", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("healthcare_portal_message", Domain.HEALTHCARE, "Patient sending message through portal", [PIICategory.PERSON]),

    # Pharmacy
    Topic("pharmacy_pickup", Domain.HEALTHCARE, "Patient picking up prescription", [PIICategory.PERSON]),
    Topic("pharmacy_delivery", Domain.HEALTHCARE, "Patient setting up prescription delivery", [PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("pharmacy_hours", Domain.HEALTHCARE, "Patient asking about pharmacy hours", []),
    Topic("pharmacy_vaccine", Domain.HEALTHCARE, "Patient scheduling vaccination", [PIICategory.PERSON, PIICategory.CONTACT]),

    # Urgent/Emergency
    Topic("healthcare_urgent_care", Domain.HEALTHCARE, "Patient asking about urgent care options", []),
    Topic("healthcare_er_wait_time", Domain.HEALTHCARE, "Patient asking about ER wait times", []),
    Topic("healthcare_nurse_line", Domain.HEALTHCARE, "Patient consulting with nurse hotline", [PIICategory.PERSON, PIICategory.MEDICAL]),

    # Administrative
    Topic("healthcare_new_patient", Domain.HEALTHCARE, "New patient registration", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.GOV_ID]),
    Topic("healthcare_update_info", Domain.HEALTHCARE, "Patient updating personal information", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("healthcare_hipaa_request", Domain.HEALTHCARE, "Patient making HIPAA-related request", [PIICategory.PERSON]),
    Topic("healthcare_authorized_rep", Domain.HEALTHCARE, "Setting up authorized representative", [PIICategory.PERSON, PIICategory.GOV_ID]),
]

# =============================================================================
# TECH SUPPORT (~150 topics)
# =============================================================================

TECH_SUPPORT_TOPICS = [
    # Account Access
    Topic("tech_password_reset", Domain.TECH_SUPPORT, "User forgot password needs reset", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("tech_account_locked", Domain.TECH_SUPPORT, "User account is locked", [PIICategory.CONTACT]),
    Topic("tech_account_hacked", Domain.TECH_SUPPORT, "User believes account was compromised", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("tech_account_recovery", Domain.TECH_SUPPORT, "User needs to recover inaccessible account", [PIICategory.CONTACT, PIICategory.PERSON]),
    Topic("tech_mfa_lost", Domain.TECH_SUPPORT, "User lost MFA device", [PIICategory.CONTACT]),
    Topic("tech_mfa_setup", Domain.TECH_SUPPORT, "User setting up two-factor authentication", [PIICategory.CONTACT]),
    Topic("tech_email_change", Domain.TECH_SUPPORT, "User changing email on account", [PIICategory.CONTACT]),
    Topic("tech_username_change", Domain.TECH_SUPPORT, "User wants to change username", [PIICategory.CONTACT]),

    # Software Issues
    Topic("tech_install_help", Domain.TECH_SUPPORT, "User needs help installing software", []),
    Topic("tech_update_failed", Domain.TECH_SUPPORT, "Software update failed or stuck", []),
    Topic("tech_crash_report", Domain.TECH_SUPPORT, "Application keeps crashing", []),
    Topic("tech_slow_performance", Domain.TECH_SUPPORT, "Application running slowly", []),
    Topic("tech_error_message", Domain.TECH_SUPPORT, "User getting error message", []),
    Topic("tech_feature_missing", Domain.TECH_SUPPORT, "Feature not working or missing", []),
    Topic("tech_compatibility", Domain.TECH_SUPPORT, "Software compatibility question", []),
    Topic("tech_license_key", Domain.TECH_SUPPORT, "User needs help with license key", [PIICategory.IDENTIFIER, PIICategory.CREDENTIALS]),
    Topic("tech_activation", Domain.TECH_SUPPORT, "User having trouble activating software", [PIICategory.IDENTIFIER]),

    # Device Issues
    Topic("tech_device_setup", Domain.TECH_SUPPORT, "User setting up new device", []),
    Topic("tech_device_not_working", Domain.TECH_SUPPORT, "Device stopped working", [PIICategory.IDENTIFIER]),
    Topic("tech_device_wont_turn_on", Domain.TECH_SUPPORT, "Device won't power on", [PIICategory.IDENTIFIER]),
    Topic("tech_device_overheating", Domain.TECH_SUPPORT, "Device is overheating", [PIICategory.IDENTIFIER]),
    Topic("tech_battery_issue", Domain.TECH_SUPPORT, "Battery draining too fast or not charging", [PIICategory.IDENTIFIER]),
    Topic("tech_screen_issue", Domain.TECH_SUPPORT, "Display or screen problems", [PIICategory.IDENTIFIER]),
    Topic("tech_audio_issue", Domain.TECH_SUPPORT, "Audio not working or distorted", [PIICategory.IDENTIFIER]),
    Topic("tech_camera_issue", Domain.TECH_SUPPORT, "Camera not working", [PIICategory.IDENTIFIER]),

    # Connectivity
    Topic("tech_wifi_issue", Domain.TECH_SUPPORT, "WiFi not connecting or slow", []),
    Topic("tech_bluetooth_issue", Domain.TECH_SUPPORT, "Bluetooth pairing problems", []),
    Topic("tech_internet_slow", Domain.TECH_SUPPORT, "Internet connection is slow", []),
    Topic("tech_vpn_issue", Domain.TECH_SUPPORT, "VPN not connecting", [PIICategory.CREDENTIALS]),
    Topic("tech_printer_setup", Domain.TECH_SUPPORT, "Setting up or connecting printer", []),
    Topic("tech_printer_issue", Domain.TECH_SUPPORT, "Printer not working", []),

    # Data and Storage
    Topic("tech_data_recovery", Domain.TECH_SUPPORT, "User needs to recover lost data", []),
    Topic("tech_backup_help", Domain.TECH_SUPPORT, "User needs help with backups", []),
    Topic("tech_storage_full", Domain.TECH_SUPPORT, "Device storage is full", []),
    Topic("tech_file_sync", Domain.TECH_SUPPORT, "Files not syncing properly", [PIICategory.CONTACT]),
    Topic("tech_transfer_data", Domain.TECH_SUPPORT, "Transferring data to new device", []),

    # Subscription and Billing
    Topic("tech_subscription_start", Domain.TECH_SUPPORT, "User subscribing to service", [PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("tech_subscription_cancel", Domain.TECH_SUPPORT, "User canceling subscription", [PIICategory.CONTACT]),
    Topic("tech_subscription_upgrade", Domain.TECH_SUPPORT, "User upgrading subscription tier", [PIICategory.CONTACT]),
    Topic("tech_subscription_downgrade", Domain.TECH_SUPPORT, "User downgrading subscription", [PIICategory.CONTACT]),
    Topic("tech_refund_request", Domain.TECH_SUPPORT, "User requesting refund", [PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("tech_billing_issue", Domain.TECH_SUPPORT, "User has billing question or issue", [PIICategory.CONTACT, PIICategory.FINANCIAL]),

    # Security
    Topic("tech_security_concern", Domain.TECH_SUPPORT, "User has security concerns", [PIICategory.CONTACT]),
    Topic("tech_suspicious_email", Domain.TECH_SUPPORT, "User received suspicious email", [PIICategory.CONTACT]),
    Topic("tech_malware_concern", Domain.TECH_SUPPORT, "User thinks device has malware", []),
    Topic("tech_privacy_settings", Domain.TECH_SUPPORT, "User needs help with privacy settings", [PIICategory.CONTACT]),
    Topic("tech_data_deletion", Domain.TECH_SUPPORT, "User wants data deleted (GDPR/CCPA)", [PIICategory.CONTACT, PIICategory.PERSON]),

    # Smart Home
    Topic("tech_smart_home_setup", Domain.TECH_SUPPORT, "Setting up smart home device", []),
    Topic("tech_smart_home_issue", Domain.TECH_SUPPORT, "Smart home device not responding", []),
    Topic("tech_voice_assistant", Domain.TECH_SUPPORT, "Voice assistant not working correctly", []),
    Topic("tech_smart_lock", Domain.TECH_SUPPORT, "Smart lock issue", []),
    Topic("tech_thermostat", Domain.TECH_SUPPORT, "Smart thermostat problems", []),

    # API and Developer
    Topic("tech_api_access", Domain.TECH_SUPPORT, "Developer requesting API access", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("tech_api_key_issue", Domain.TECH_SUPPORT, "API key not working", [PIICategory.CREDENTIALS]),
    Topic("tech_api_rate_limit", Domain.TECH_SUPPORT, "Developer hitting rate limits", [PIICategory.IDENTIFIER]),
    Topic("tech_webhook_issue", Domain.TECH_SUPPORT, "Webhook not receiving events", [PIICategory.CREDENTIALS]),
    Topic("tech_integration_help", Domain.TECH_SUPPORT, "Help with third-party integration", [PIICategory.CREDENTIALS]),
]

# =============================================================================
# TRAVEL / HOSPITALITY (~100 topics)
# =============================================================================

TRAVEL_TOPICS = [
    # Flight Reservations
    Topic("travel_flight_book", Domain.TRAVEL, "Customer booking flight", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("travel_flight_change", Domain.TRAVEL, "Customer changing flight reservation", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("travel_flight_cancel", Domain.TRAVEL, "Customer canceling flight", [PIICategory.IDENTIFIER]),
    Topic("travel_flight_status", Domain.TRAVEL, "Customer checking flight status", [PIICategory.IDENTIFIER]),
    Topic("travel_seat_selection", Domain.TRAVEL, "Customer selecting or changing seat", [PIICategory.IDENTIFIER]),
    Topic("travel_upgrade_request", Domain.TRAVEL, "Customer requesting upgrade", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("travel_special_meal", Domain.TRAVEL, "Customer requesting special meal", [PIICategory.IDENTIFIER]),
    Topic("travel_add_passenger", Domain.TRAVEL, "Adding passenger to reservation", [PIICategory.PERSON, PIICategory.IDENTIFIER]),

    # Baggage
    Topic("travel_baggage_allowance", Domain.TRAVEL, "Customer asking about baggage allowance", []),
    Topic("travel_baggage_add", Domain.TRAVEL, "Customer adding checked bag", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("travel_baggage_lost", Domain.TRAVEL, "Customer reporting lost luggage", [PIICategory.IDENTIFIER, PIICategory.CONTACT]),
    Topic("travel_baggage_delayed", Domain.TRAVEL, "Customer tracking delayed baggage", [PIICategory.IDENTIFIER]),
    Topic("travel_baggage_damaged", Domain.TRAVEL, "Customer reporting damaged luggage", [PIICategory.IDENTIFIER]),

    # Hotel
    Topic("travel_hotel_book", Domain.TRAVEL, "Customer booking hotel room", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("travel_hotel_modify", Domain.TRAVEL, "Customer modifying hotel reservation", [PIICategory.IDENTIFIER]),
    Topic("travel_hotel_cancel", Domain.TRAVEL, "Customer canceling hotel booking", [PIICategory.IDENTIFIER]),
    Topic("travel_hotel_checkin", Domain.TRAVEL, "Customer asking about check-in", [PIICategory.IDENTIFIER]),
    Topic("travel_hotel_checkout", Domain.TRAVEL, "Customer asking about check-out", [PIICategory.IDENTIFIER]),
    Topic("travel_hotel_amenities", Domain.TRAVEL, "Customer asking about hotel amenities", []),
    Topic("travel_hotel_room_issue", Domain.TRAVEL, "Customer has issue with room", [PIICategory.IDENTIFIER]),
    Topic("travel_hotel_request", Domain.TRAVEL, "Customer making special request", [PIICategory.IDENTIFIER]),

    # Car Rental
    Topic("travel_car_book", Domain.TRAVEL, "Customer booking rental car", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("travel_car_modify", Domain.TRAVEL, "Customer modifying car reservation", [PIICategory.IDENTIFIER]),
    Topic("travel_car_cancel", Domain.TRAVEL, "Customer canceling car rental", [PIICategory.IDENTIFIER]),
    Topic("travel_car_extend", Domain.TRAVEL, "Customer extending car rental", [PIICategory.IDENTIFIER]),
    Topic("travel_car_pickup", Domain.TRAVEL, "Customer asking about car pickup", [PIICategory.IDENTIFIER]),
    Topic("travel_car_return", Domain.TRAVEL, "Customer asking about car return", [PIICategory.IDENTIFIER]),
    Topic("travel_car_insurance", Domain.TRAVEL, "Customer asking about rental insurance", []),
    Topic("travel_car_toll", Domain.TRAVEL, "Customer has toll charge question", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),

    # Loyalty Programs
    Topic("travel_loyalty_join", Domain.TRAVEL, "Customer joining loyalty program", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("travel_loyalty_points", Domain.TRAVEL, "Customer checking points balance", [PIICategory.IDENTIFIER]),
    Topic("travel_loyalty_redeem", Domain.TRAVEL, "Customer redeeming points", [PIICategory.IDENTIFIER]),
    Topic("travel_loyalty_status", Domain.TRAVEL, "Customer asking about elite status", [PIICategory.IDENTIFIER]),
    Topic("travel_loyalty_missing", Domain.TRAVEL, "Customer missing points from trip", [PIICategory.IDENTIFIER]),
    Topic("travel_loyalty_transfer", Domain.TRAVEL, "Customer transferring points", [PIICategory.IDENTIFIER]),

    # Vacation Packages
    Topic("travel_package_inquiry", Domain.TRAVEL, "Customer asking about vacation packages", []),
    Topic("travel_package_book", Domain.TRAVEL, "Customer booking vacation package", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.FINANCIAL]),
    Topic("travel_cruise_inquiry", Domain.TRAVEL, "Customer asking about cruises", []),
    Topic("travel_cruise_book", Domain.TRAVEL, "Customer booking cruise", [PIICategory.PERSON, PIICategory.CONTACT]),

    # Refunds and Compensation
    Topic("travel_refund_request", Domain.TRAVEL, "Customer requesting refund", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("travel_refund_status", Domain.TRAVEL, "Customer checking refund status", [PIICategory.IDENTIFIER]),
    Topic("travel_compensation", Domain.TRAVEL, "Customer seeking compensation for issue", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("travel_voucher_issue", Domain.TRAVEL, "Customer has issue with travel voucher", [PIICategory.IDENTIFIER]),

    # Travel Documents
    Topic("travel_visa_info", Domain.TRAVEL, "Customer asking about visa requirements", []),
    Topic("travel_passport_info", Domain.TRAVEL, "Customer asking about passport requirements", [PIICategory.GOV_ID]),
    Topic("travel_covid_requirements", Domain.TRAVEL, "Customer asking about travel health requirements", []),
]

# =============================================================================
# TELECOMMUNICATIONS (~100 topics)
# =============================================================================

TELECOM_TOPICS = [
    # Service Plans
    Topic("telecom_plan_inquiry", Domain.TELECOM, "Customer asking about available plans", []),
    Topic("telecom_plan_change", Domain.TELECOM, "Customer changing service plan", [PIICategory.IDENTIFIER]),
    Topic("telecom_plan_upgrade", Domain.TELECOM, "Customer upgrading to higher tier", [PIICategory.IDENTIFIER]),
    Topic("telecom_plan_downgrade", Domain.TELECOM, "Customer downgrading plan", [PIICategory.IDENTIFIER]),
    Topic("telecom_new_line", Domain.TELECOM, "Customer adding new line to account", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("telecom_remove_line", Domain.TELECOM, "Customer removing line from account", [PIICategory.IDENTIFIER]),

    # Device
    Topic("telecom_device_upgrade", Domain.TELECOM, "Customer upgrading phone", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("telecom_device_activate", Domain.TELECOM, "Customer activating new device", [PIICategory.IDENTIFIER]),
    Topic("telecom_device_trade_in", Domain.TELECOM, "Customer trading in old device", [PIICategory.IDENTIFIER]),
    Topic("telecom_device_unlock", Domain.TELECOM, "Customer requesting device unlock", [PIICategory.IDENTIFIER]),
    Topic("telecom_sim_issue", Domain.TELECOM, "Customer has SIM card issue", [PIICategory.IDENTIFIER]),
    Topic("telecom_esim_setup", Domain.TELECOM, "Customer setting up eSIM", [PIICategory.IDENTIFIER]),
    Topic("telecom_device_protection", Domain.TELECOM, "Customer asking about device insurance", [PIICategory.IDENTIFIER]),
    Topic("telecom_device_claim", Domain.TELECOM, "Customer filing device insurance claim", [PIICategory.IDENTIFIER]),

    # Billing
    Topic("telecom_bill_inquiry", Domain.TELECOM, "Customer asking about bill", [PIICategory.IDENTIFIER]),
    Topic("telecom_bill_payment", Domain.TELECOM, "Customer making payment", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("telecom_bill_dispute", Domain.TELECOM, "Customer disputing charge", [PIICategory.IDENTIFIER]),
    Topic("telecom_autopay_setup", Domain.TELECOM, "Customer setting up autopay", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("telecom_payment_arrangement", Domain.TELECOM, "Customer arranging payment plan", [PIICategory.IDENTIFIER]),
    Topic("telecom_balance_due", Domain.TELECOM, "Customer checking balance due", [PIICategory.IDENTIFIER]),

    # Service Issues
    Topic("telecom_no_service", Domain.TELECOM, "Customer has no service/signal", [PIICategory.LOCATION]),
    Topic("telecom_dropped_calls", Domain.TELECOM, "Customer experiencing dropped calls", [PIICategory.IDENTIFIER]),
    Topic("telecom_slow_data", Domain.TELECOM, "Customer has slow data speeds", [PIICategory.IDENTIFIER]),
    Topic("telecom_outage", Domain.TELECOM, "Customer asking about service outage", [PIICategory.LOCATION]),
    Topic("telecom_coverage_check", Domain.TELECOM, "Customer checking coverage in area", [PIICategory.LOCATION]),
    Topic("telecom_signal_booster", Domain.TELECOM, "Customer asking about signal boosters", []),

    # Usage
    Topic("telecom_data_usage", Domain.TELECOM, "Customer checking data usage", [PIICategory.IDENTIFIER]),
    Topic("telecom_data_overage", Domain.TELECOM, "Customer has data overage charges", [PIICategory.IDENTIFIER]),
    Topic("telecom_add_data", Domain.TELECOM, "Customer adding more data", [PIICategory.IDENTIFIER]),
    Topic("telecom_unlimited_inquiry", Domain.TELECOM, "Customer asking about unlimited plans", []),

    # International
    Topic("telecom_international_plan", Domain.TELECOM, "Customer adding international plan", [PIICategory.IDENTIFIER]),
    Topic("telecom_roaming_charges", Domain.TELECOM, "Customer asking about roaming charges", [PIICategory.IDENTIFIER]),
    Topic("telecom_international_call", Domain.TELECOM, "Customer making international calls", [PIICategory.IDENTIFIER]),

    # Account
    Topic("telecom_account_setup", Domain.TELECOM, "New customer setting up account", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.GOV_ID]),
    Topic("telecom_account_access", Domain.TELECOM, "Customer accessing online account", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),
    Topic("telecom_account_transfer", Domain.TELECOM, "Customer transferring account ownership", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("telecom_authorized_user", Domain.TELECOM, "Customer adding authorized user", [PIICategory.PERSON]),
    Topic("telecom_account_pin", Domain.TELECOM, "Customer resetting account PIN", [PIICategory.CREDENTIALS]),

    # Features
    Topic("telecom_voicemail_setup", Domain.TELECOM, "Customer setting up voicemail", [PIICategory.IDENTIFIER]),
    Topic("telecom_call_forwarding", Domain.TELECOM, "Customer setting up call forwarding", [PIICategory.CONTACT]),
    Topic("telecom_caller_id", Domain.TELECOM, "Customer asking about caller ID", []),
    Topic("telecom_block_number", Domain.TELECOM, "Customer blocking a number", [PIICategory.CONTACT]),
    Topic("telecom_spam_block", Domain.TELECOM, "Customer setting up spam blocking", []),

    # Internet/Home
    Topic("telecom_internet_inquiry", Domain.TELECOM, "Customer asking about home internet", [PIICategory.LOCATION]),
    Topic("telecom_internet_install", Domain.TELECOM, "Customer scheduling internet installation", [PIICategory.LOCATION, PIICategory.CONTACT]),
    Topic("telecom_internet_issue", Domain.TELECOM, "Customer has internet connectivity issue", [PIICategory.IDENTIFIER]),
    Topic("telecom_wifi_help", Domain.TELECOM, "Customer needs WiFi help", [PIICategory.CREDENTIALS]),
    Topic("telecom_router_issue", Domain.TELECOM, "Customer has router problem", [PIICategory.IDENTIFIER]),
    Topic("telecom_speed_test", Domain.TELECOM, "Customer reporting slow speeds", [PIICategory.IDENTIFIER]),
]

# =============================================================================
# UTILITIES (~80 topics)
# =============================================================================

UTILITIES_TOPICS = [
    # Billing
    Topic("utility_bill_inquiry", Domain.UTILITIES, "Customer asking about utility bill", [PIICategory.IDENTIFIER]),
    Topic("utility_bill_payment", Domain.UTILITIES, "Customer making bill payment", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("utility_bill_high", Domain.UTILITIES, "Customer asking why bill is higher than usual", [PIICategory.IDENTIFIER]),
    Topic("utility_budget_billing", Domain.UTILITIES, "Customer asking about budget billing", [PIICategory.IDENTIFIER]),
    Topic("utility_autopay_setup", Domain.UTILITIES, "Customer setting up automatic payments", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("utility_payment_extension", Domain.UTILITIES, "Customer requesting payment extension", [PIICategory.IDENTIFIER]),
    Topic("utility_payment_plan", Domain.UTILITIES, "Customer setting up payment arrangement", [PIICategory.IDENTIFIER]),
    Topic("utility_paperless_billing", Domain.UTILITIES, "Customer switching to paperless billing", [PIICategory.CONTACT]),

    # Service Start/Stop
    Topic("utility_start_service", Domain.UTILITIES, "Customer starting new utility service", [PIICategory.PERSON, PIICategory.CONTACT, PIICategory.LOCATION]),
    Topic("utility_stop_service", Domain.UTILITIES, "Customer discontinuing service", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("utility_transfer_service", Domain.UTILITIES, "Customer transferring service to new address", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("utility_temporary_disconnect", Domain.UTILITIES, "Customer requesting temporary disconnect", [PIICategory.IDENTIFIER]),
    Topic("utility_reconnect", Domain.UTILITIES, "Customer requesting service reconnection", [PIICategory.IDENTIFIER]),

    # Outages
    Topic("utility_outage_report", Domain.UTILITIES, "Customer reporting outage", [PIICategory.LOCATION]),
    Topic("utility_outage_status", Domain.UTILITIES, "Customer checking outage status", [PIICategory.LOCATION]),
    Topic("utility_outage_eta", Domain.UTILITIES, "Customer asking when power will be restored", [PIICategory.LOCATION]),
    Topic("utility_planned_outage", Domain.UTILITIES, "Customer asking about planned outage", [PIICategory.LOCATION]),

    # Meter
    Topic("utility_meter_reading", Domain.UTILITIES, "Customer submitting meter reading", [PIICategory.IDENTIFIER]),
    Topic("utility_meter_access", Domain.UTILITIES, "Customer scheduling meter access", [PIICategory.LOCATION, PIICategory.CONTACT]),
    Topic("utility_smart_meter", Domain.UTILITIES, "Customer asking about smart meter", [PIICategory.IDENTIFIER]),
    Topic("utility_meter_issue", Domain.UTILITIES, "Customer reporting meter problem", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),

    # Account
    Topic("utility_account_info", Domain.UTILITIES, "Customer updating account information", [PIICategory.CONTACT, PIICategory.LOCATION]),
    Topic("utility_account_holder", Domain.UTILITIES, "Customer changing account holder name", [PIICategory.PERSON]),
    Topic("utility_authorized_contact", Domain.UTILITIES, "Customer adding authorized contact", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("utility_online_access", Domain.UTILITIES, "Customer needs help with online account", [PIICategory.CONTACT, PIICategory.CREDENTIALS]),

    # Programs
    Topic("utility_rebate_program", Domain.UTILITIES, "Customer asking about rebate programs", []),
    Topic("utility_energy_audit", Domain.UTILITIES, "Customer scheduling energy audit", [PIICategory.LOCATION, PIICategory.CONTACT]),
    Topic("utility_assistance_program", Domain.UTILITIES, "Customer asking about bill assistance", [PIICategory.PERSON, PIICategory.FINANCIAL]),
    Topic("utility_solar_program", Domain.UTILITIES, "Customer asking about solar programs", [PIICategory.LOCATION]),
    Topic("utility_green_energy", Domain.UTILITIES, "Customer asking about green energy options", [PIICategory.IDENTIFIER]),

    # Emergencies
    Topic("utility_gas_leak", Domain.UTILITIES, "Customer reporting gas smell/leak", [PIICategory.LOCATION]),
    Topic("utility_downed_line", Domain.UTILITIES, "Customer reporting downed power line", [PIICategory.LOCATION]),
    Topic("utility_water_main_break", Domain.UTILITIES, "Customer reporting water main issue", [PIICategory.LOCATION]),

    # Water Specific
    Topic("utility_water_quality", Domain.UTILITIES, "Customer asking about water quality", [PIICategory.LOCATION]),
    Topic("utility_water_pressure", Domain.UTILITIES, "Customer reporting water pressure issue", [PIICategory.LOCATION]),
    Topic("utility_water_shutoff", Domain.UTILITIES, "Customer asking about water shutoff valve", [PIICategory.LOCATION]),
]

# =============================================================================
# INSURANCE (~100 topics)
# =============================================================================

INSURANCE_TOPICS = [
    # Quotes and Policies
    Topic("insurance_quote_auto", Domain.INSURANCE, "Customer getting auto insurance quote", [PIICategory.PERSON, PIICategory.GOV_ID, PIICategory.LOCATION]),
    Topic("insurance_quote_home", Domain.INSURANCE, "Customer getting home insurance quote", [PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("insurance_quote_life", Domain.INSURANCE, "Customer getting life insurance quote", [PIICategory.PERSON, PIICategory.MEDICAL]),
    Topic("insurance_quote_health", Domain.INSURANCE, "Customer getting health insurance quote", [PIICategory.PERSON]),
    Topic("insurance_buy_policy", Domain.INSURANCE, "Customer purchasing insurance policy", [PIICategory.PERSON, PIICategory.FINANCIAL]),
    Topic("insurance_policy_details", Domain.INSURANCE, "Customer asking about policy coverage", [PIICategory.IDENTIFIER]),
    Topic("insurance_policy_change", Domain.INSURANCE, "Customer modifying policy", [PIICategory.IDENTIFIER]),
    Topic("insurance_policy_cancel", Domain.INSURANCE, "Customer canceling policy", [PIICategory.IDENTIFIER]),
    Topic("insurance_policy_renew", Domain.INSURANCE, "Customer renewing policy", [PIICategory.IDENTIFIER]),

    # Claims
    Topic("insurance_claim_file", Domain.INSURANCE, "Customer filing insurance claim", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("insurance_claim_status", Domain.INSURANCE, "Customer checking claim status", [PIICategory.IDENTIFIER]),
    Topic("insurance_claim_documents", Domain.INSURANCE, "Customer submitting claim documents", [PIICategory.IDENTIFIER]),
    Topic("insurance_claim_dispute", Domain.INSURANCE, "Customer disputing claim decision", [PIICategory.IDENTIFIER]),
    Topic("insurance_auto_accident", Domain.INSURANCE, "Customer reporting auto accident", [PIICategory.IDENTIFIER, PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("insurance_home_damage", Domain.INSURANCE, "Customer reporting home damage", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
    Topic("insurance_theft_claim", Domain.INSURANCE, "Customer reporting theft", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),

    # Billing
    Topic("insurance_premium_inquiry", Domain.INSURANCE, "Customer asking about premium", [PIICategory.IDENTIFIER]),
    Topic("insurance_payment_make", Domain.INSURANCE, "Customer making premium payment", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("insurance_payment_history", Domain.INSURANCE, "Customer checking payment history", [PIICategory.IDENTIFIER]),
    Topic("insurance_payment_plan", Domain.INSURANCE, "Customer setting up payment plan", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),
    Topic("insurance_autopay", Domain.INSURANCE, "Customer setting up autopay", [PIICategory.IDENTIFIER, PIICategory.FINANCIAL]),

    # Coverage
    Topic("insurance_add_driver", Domain.INSURANCE, "Customer adding driver to policy", [PIICategory.IDENTIFIER, PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("insurance_add_vehicle", Domain.INSURANCE, "Customer adding vehicle to policy", [PIICategory.IDENTIFIER]),
    Topic("insurance_remove_driver", Domain.INSURANCE, "Customer removing driver from policy", [PIICategory.IDENTIFIER, PIICategory.PERSON]),
    Topic("insurance_coverage_increase", Domain.INSURANCE, "Customer increasing coverage limits", [PIICategory.IDENTIFIER]),
    Topic("insurance_deductible_change", Domain.INSURANCE, "Customer changing deductible", [PIICategory.IDENTIFIER]),
    Topic("insurance_beneficiary_update", Domain.INSURANCE, "Customer updating beneficiary", [PIICategory.IDENTIFIER, PIICategory.PERSON]),

    # Documents
    Topic("insurance_id_card", Domain.INSURANCE, "Customer needs insurance ID card", [PIICategory.IDENTIFIER]),
    Topic("insurance_proof", Domain.INSURANCE, "Customer needs proof of insurance", [PIICategory.IDENTIFIER]),
    Topic("insurance_declaration_page", Domain.INSURANCE, "Customer needs declaration page", [PIICategory.IDENTIFIER]),

    # Discounts
    Topic("insurance_discount_inquiry", Domain.INSURANCE, "Customer asking about available discounts", [PIICategory.IDENTIFIER]),
    Topic("insurance_bundle_discount", Domain.INSURANCE, "Customer asking about bundling policies", [PIICategory.IDENTIFIER]),
    Topic("insurance_safe_driver", Domain.INSURANCE, "Customer asking about safe driver discount", [PIICategory.IDENTIFIER]),
]

# =============================================================================
# GOVERNMENT SERVICES (~80 topics)
# =============================================================================

GOVERNMENT_TOPICS = [
    # Identity Documents
    Topic("gov_drivers_license_renew", Domain.GOVERNMENT, "Citizen renewing driver's license", [PIICategory.PERSON, PIICategory.GOV_ID, PIICategory.LOCATION]),
    Topic("gov_drivers_license_replace", Domain.GOVERNMENT, "Citizen replacing lost license", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_id_card", Domain.GOVERNMENT, "Citizen getting state ID card", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_passport_apply", Domain.GOVERNMENT, "Citizen applying for passport", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_passport_renew", Domain.GOVERNMENT, "Citizen renewing passport", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_birth_certificate", Domain.GOVERNMENT, "Citizen requesting birth certificate", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_ssn_replace", Domain.GOVERNMENT, "Citizen replacing Social Security card", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_name_change", Domain.GOVERNMENT, "Citizen updating name on government documents", [PIICategory.PERSON, PIICategory.GOV_ID]),

    # Vehicle Registration
    Topic("gov_vehicle_register", Domain.GOVERNMENT, "Citizen registering vehicle", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("gov_vehicle_renew", Domain.GOVERNMENT, "Citizen renewing vehicle registration", [PIICategory.IDENTIFIER]),
    Topic("gov_vehicle_title", Domain.GOVERNMENT, "Citizen getting vehicle title", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("gov_license_plate", Domain.GOVERNMENT, "Citizen getting license plates", [PIICategory.IDENTIFIER]),

    # Taxes
    Topic("gov_tax_filing", Domain.GOVERNMENT, "Citizen asking about tax filing", [PIICategory.GOV_ID]),
    Topic("gov_tax_refund", Domain.GOVERNMENT, "Citizen checking tax refund status", [PIICategory.GOV_ID, PIICategory.FINANCIAL]),
    Topic("gov_tax_payment", Domain.GOVERNMENT, "Citizen making tax payment", [PIICategory.GOV_ID, PIICategory.FINANCIAL]),
    Topic("gov_tax_transcript", Domain.GOVERNMENT, "Citizen requesting tax transcript", [PIICategory.GOV_ID]),
    Topic("gov_property_tax", Domain.GOVERNMENT, "Citizen asking about property tax", [PIICategory.LOCATION, PIICategory.IDENTIFIER]),

    # Benefits
    Topic("gov_benefits_apply", Domain.GOVERNMENT, "Citizen applying for benefits", [PIICategory.PERSON, PIICategory.GOV_ID, PIICategory.FINANCIAL]),
    Topic("gov_benefits_status", Domain.GOVERNMENT, "Citizen checking benefits status", [PIICategory.IDENTIFIER]),
    Topic("gov_unemployment", Domain.GOVERNMENT, "Citizen asking about unemployment", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_disability", Domain.GOVERNMENT, "Citizen asking about disability benefits", [PIICategory.PERSON, PIICategory.GOV_ID, PIICategory.MEDICAL]),
    Topic("gov_medicare", Domain.GOVERNMENT, "Citizen asking about Medicare", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_social_security", Domain.GOVERNMENT, "Citizen asking about Social Security benefits", [PIICategory.PERSON, PIICategory.GOV_ID]),

    # Records
    Topic("gov_court_records", Domain.GOVERNMENT, "Citizen requesting court records", [PIICategory.PERSON]),
    Topic("gov_criminal_record", Domain.GOVERNMENT, "Citizen requesting background check", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_marriage_license", Domain.GOVERNMENT, "Citizen getting marriage license", [PIICategory.PERSON, PIICategory.GOV_ID]),
    Topic("gov_death_certificate", Domain.GOVERNMENT, "Citizen requesting death certificate", [PIICategory.PERSON]),

    # Permits
    Topic("gov_building_permit", Domain.GOVERNMENT, "Citizen applying for building permit", [PIICategory.LOCATION, PIICategory.PERSON]),
    Topic("gov_business_license", Domain.GOVERNMENT, "Citizen getting business license", [PIICategory.PERSON, PIICategory.LOCATION]),
    Topic("gov_parking_permit", Domain.GOVERNMENT, "Citizen getting parking permit", [PIICategory.IDENTIFIER, PIICategory.LOCATION]),
]

# =============================================================================
# GENERAL Q&A (~120 topics)
# =============================================================================

GENERAL_TOPICS = [
    # Hours and Location
    Topic("general_store_hours", Domain.GENERAL, "Customer asking about business hours", []),
    Topic("general_holiday_hours", Domain.GENERAL, "Customer asking about holiday hours", []),
    Topic("general_location_find", Domain.GENERAL, "Customer looking for nearest location", []),
    Topic("general_directions", Domain.GENERAL, "Customer asking for directions", []),
    Topic("general_parking", Domain.GENERAL, "Customer asking about parking", []),

    # Policies
    Topic("general_return_policy", Domain.GENERAL, "Customer asking about return policy", []),
    Topic("general_warranty_policy", Domain.GENERAL, "Customer asking about warranty policy", []),
    Topic("general_privacy_policy", Domain.GENERAL, "Customer asking about privacy policy", []),
    Topic("general_terms_of_service", Domain.GENERAL, "Customer asking about terms of service", []),
    Topic("general_cancellation_policy", Domain.GENERAL, "Customer asking about cancellation policy", []),

    # Contact
    Topic("general_contact_info", Domain.GENERAL, "Customer asking how to contact company", []),
    Topic("general_speak_manager", Domain.GENERAL, "Customer wanting to speak with manager", []),
    Topic("general_department_transfer", Domain.GENERAL, "Customer needing different department", []),
    Topic("general_callback_request", Domain.GENERAL, "Customer requesting callback", [PIICategory.CONTACT]),
    Topic("general_schedule_call", Domain.GENERAL, "Customer scheduling phone appointment", [PIICategory.CONTACT]),

    # Information
    Topic("general_product_info", Domain.GENERAL, "Customer asking general product information", []),
    Topic("general_service_info", Domain.GENERAL, "Customer asking about available services", []),
    Topic("general_pricing_info", Domain.GENERAL, "Customer asking about pricing", []),
    Topic("general_company_info", Domain.GENERAL, "Customer asking about company", []),
    Topic("general_career_inquiry", Domain.GENERAL, "Customer asking about job opportunities", []),

    # Complaints and Feedback
    Topic("general_complaint_submit", Domain.GENERAL, "Customer submitting complaint", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("general_feedback_positive", Domain.GENERAL, "Customer providing positive feedback", []),
    Topic("general_feedback_suggestion", Domain.GENERAL, "Customer making suggestion", []),
    Topic("general_escalation_request", Domain.GENERAL, "Customer requesting escalation", [PIICategory.IDENTIFIER]),

    # Appointments
    Topic("general_appointment_schedule", Domain.GENERAL, "Customer scheduling appointment", [PIICategory.PERSON, PIICategory.CONTACT]),
    Topic("general_appointment_reschedule", Domain.GENERAL, "Customer rescheduling appointment", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("general_appointment_cancel", Domain.GENERAL, "Customer canceling appointment", [PIICategory.PERSON, PIICategory.IDENTIFIER]),
    Topic("general_appointment_confirm", Domain.GENERAL, "Customer confirming appointment", [PIICategory.PERSON]),

    # Wait Times
    Topic("general_wait_time", Domain.GENERAL, "Customer asking about current wait time", []),
    Topic("general_queue_position", Domain.GENERAL, "Customer asking about queue position", []),
    Topic("general_busy_times", Domain.GENERAL, "Customer asking about best times to visit/call", []),

    # Accessibility
    Topic("general_accessibility", Domain.GENERAL, "Customer asking about accessibility options", []),
    Topic("general_language_support", Domain.GENERAL, "Customer asking about language support", []),
    Topic("general_tty_service", Domain.GENERAL, "Customer asking about TTY/relay services", []),

    # Miscellaneous
    Topic("general_website_issue", Domain.GENERAL, "Customer reporting website problem", []),
    Topic("general_app_issue", Domain.GENERAL, "Customer reporting mobile app issue", []),
    Topic("general_how_to", Domain.GENERAL, "Customer asking how to do something", []),
    Topic("general_status_check", Domain.GENERAL, "Customer checking on status of something", [PIICategory.IDENTIFIER]),
    Topic("general_confirmation_request", Domain.GENERAL, "Customer requesting confirmation", [PIICategory.IDENTIFIER]),
]

# =============================================================================
# Combine all topics
# =============================================================================

ALL_TOPICS: list[Topic] = (
    RETAIL_TOPICS
    + BANKING_TOPICS
    + HEALTHCARE_TOPICS
    + TECH_SUPPORT_TOPICS
    + TRAVEL_TOPICS
    + TELECOM_TOPICS
    + UTILITIES_TOPICS
    + INSURANCE_TOPICS
    + GOVERNMENT_TOPICS
    + GENERAL_TOPICS
)

# Index by domain for filtered sampling
TOPICS_BY_DOMAIN: dict[Domain, list[Topic]] = {}
for topic in ALL_TOPICS:
    if topic.domain not in TOPICS_BY_DOMAIN:
        TOPICS_BY_DOMAIN[topic.domain] = []
    TOPICS_BY_DOMAIN[topic.domain].append(topic)

# Index by PII category for targeted generation
TOPICS_BY_PII: dict[PIICategory, list[Topic]] = {cat: [] for cat in PIICategory}
for topic in ALL_TOPICS:
    for pii_cat in topic.typical_pii:
        TOPICS_BY_PII[pii_cat].append(topic)


def get_random_topic(domain: Domain | None = None) -> Topic:
    """Get a random topic, optionally filtered by domain."""
    if domain:
        return random.choice(TOPICS_BY_DOMAIN[domain])
    return random.choice(ALL_TOPICS)


def get_topic_for_pii_category(category: PIICategory) -> Topic:
    """Get a random topic that typically involves the given PII category."""
    topics = TOPICS_BY_PII.get(category, [])
    if not topics:
        return random.choice(ALL_TOPICS)
    return random.choice(topics)


def get_topic_without_pii() -> Topic:
    """Get a random topic that typically doesn't involve any PII."""
    no_pii_topics = [t for t in ALL_TOPICS if not t.typical_pii]
    if not no_pii_topics:
        # Fallback to general topics which are less likely to have PII
        return random.choice(GENERAL_TOPICS)
    return random.choice(no_pii_topics)


if __name__ == "__main__":
    # Print stats
    print(f"Total topics: {len(ALL_TOPICS)}")
    print("\nTopics by domain:")
    for domain, topics in TOPICS_BY_DOMAIN.items():
        print(f"  {domain.value}: {len(topics)}")

    print("\nTopics by PII category:")
    for cat, topics in TOPICS_BY_PII.items():
        print(f"  {cat.value}: {len(topics)}")

    print("\nTopics with no typical PII:")
    no_pii = [t for t in ALL_TOPICS if not t.typical_pii]
    print(f"  {len(no_pii)} topics")
