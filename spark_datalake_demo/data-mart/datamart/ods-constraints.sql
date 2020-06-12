ALTER TABLE ods.hsg_workflow_task ADD CONSTRAINT hsg_workflow_task_ix_ak1 UNIQUE (wkfl_task_id);
ALTER TABLE ods.hsg_project_document ADD CONSTRAINT hsg_project_document_ix_ak1 UNIQUE (proj_doc_id);
ALTER TABLE ods.hsg_call_quality_program ADD CONSTRAINT hsg_call_quality_program_ix_ak UNIQUE (cq_prog_id);
ALTER TABLE ods.vendor ADD CONSTRAINT vendor_ix_pk PRIMARY KEY (vend_key);
ALTER TABLE ods.spl_hsg_issue_list ADD CONSTRAINT spl_hsg_issue_list_ix_pk PRIMARY KEY (iss_list_key);
ALTER TABLE ods.spl_hsg_daily_tasks_maint ADD CONSTRAINT spl_hsg_daily_tasks_maint_pk PRIMARY KEY (id, curr_row_flg);
ALTER TABLE ods.spl_hsg_complaints ADD CONSTRAINT spl_hsg_complaints_ix_pk PRIMARY KEY (cmplnt_key);
ALTER TABLE ods.spl_hsg_change_control_old ADD CONSTRAINT spl_hsg_change_cntl_ix_pk PRIMARY KEY (chg_cntl_key);
ALTER TABLE ods.spl_hsg_change_control ADD CONSTRAINT spl_hsg_change_control_ix_pk PRIMARY KEY (chg_cntl_key);
ALTER TABLE ods.projects ADD CONSTRAINT projects_ix_pk PRIMARY KEY (proj_key);
ALTER TABLE ods.product_line ADD CONSTRAINT product_line_ix_pk PRIMARY KEY (prod_line_key);
ALTER TABLE ods.pmo_tasks ADD CONSTRAINT pmo_tasks_ix_pk PRIMARY KEY (pmo_tasks_key);
ALTER TABLE ods.market_timing ADD CONSTRAINT market_timing_ix_pk PRIMARY KEY (mkt_tmng_key);
ALTER TABLE ods.ipm_meetings ADD CONSTRAINT ipm_meetings_ix_pk PRIMARY KEY (ipm_mtg_key);
ALTER TABLE ods.ipm_manager_updates ADD CONSTRAINT ipm_manager_updates_ix_pk PRIMARY KEY (ipm_mgr_updt_key);
ALTER TABLE ods.ipm_manager_analysis ADD CONSTRAINT ipm_manager_analysis_ix_pk PRIMARY KEY (ipm_mgr_anlys_key);
ALTER TABLE ods.ipm_firm_profiles ADD CONSTRAINT ipm_firm_profiles_ix_pk PRIMARY KEY (ipm_firm_prof_key);
ALTER TABLE ods.invoice ADD CONSTRAINT invoice_ix_pk PRIMARY KEY (invc_key);
ALTER TABLE ods.hsg_workflow_task ADD CONSTRAINT hsg_workflow_task_ix_pk PRIMARY KEY (wkfl_task_key);
ALTER TABLE ods.hsg_project_document ADD CONSTRAINT hsg_project_document_ix_pk PRIMARY KEY (hsg_proj_doc_key);
ALTER TABLE ods.hsg_dealer_fee_analysis ADD CONSTRAINT hsg_dealer_fee_analysis_ix_pk PRIMARY KEY (dlr_fee_anlys_key);
ALTER TABLE ods.hsg_control_documents ADD CONSTRAINT hsg_control_documents_ix_pk PRIMARY KEY (hsg_cntl_doc_key);
ALTER TABLE ods.hsg_control_document ADD CONSTRAINT hsg_control_document_ix_pk PRIMARY KEY (cntl_doc_key);
ALTER TABLE ods.hsg_control_doc_line ADD CONSTRAINT hsg_control_doc_line_ix_pk PRIMARY KEY (cntl_doc_line_key);
ALTER TABLE ods.hsg_control_doc_findings ADD CONSTRAINT hsg_control_doc_finding_ix_pk PRIMARY KEY (cntl_doc_fndg_key);
ALTER TABLE ods.hsg_chat_quality_result ADD CONSTRAINT hsg_chat_quality_result_ix_pk PRIMARY KEY (chat_qual_rslt_key);
ALTER TABLE ods.hsg_chat_quality_question ADD CONSTRAINT hsg_chat_question_ix_pk PRIMARY KEY (chat_qual_qstn_key);
ALTER TABLE ods.hsg_call_quality_result ADD CONSTRAINT hsg_call_quality_result_ix_pk PRIMARY KEY (cq_rslt_key);
ALTER TABLE ods.hsg_call_quality_question ADD CONSTRAINT hsg_cq_question_ix_pk PRIMARY KEY (cq_qstn_key);
ALTER TABLE ods.hsg_call_quality_program ADD CONSTRAINT hsg_call_quality_program_ix_pk PRIMARY KEY (cq_prog_key);
ALTER TABLE ods.decision_list ADD CONSTRAINT decision_list_ix_pk PRIMARY KEY (decsn_list_key);
ALTER TABLE ods.contract_review ADD CONSTRAINT contract_review_ix_pk PRIMARY KEY (contrct_revw_key);
ALTER TABLE ods.budget_line ADD CONSTRAINT budget_line_ix_pk PRIMARY KEY (bud_line_key);
ALTER TABLE ods.budget_fact ADD CONSTRAINT budget_fact_ix_pk PRIMARY KEY (bud_fact_key);
ALTER TABLE ods.budget_category ADD CONSTRAINT budget_category_ix_pk PRIMARY KEY (bud_cat_key);
ALTER TABLE ods.budget ADD CONSTRAINT budget_ix_pk PRIMARY KEY (bud_key);
ALTER TABLE ods.aml_training_history ADD CONSTRAINT aml_training_history_ix_pk PRIMARY KEY (aml_trng_hist_key);
ALTER TABLE ods.aml_sar ADD CONSTRAINT aml_sar_ix_pk PRIMARY KEY (sar_key);
ALTER TABLE ods.aml_qtrly_dealer_review ADD CONSTRAINT aml_qtrly_dealer_review_ix_pk PRIMARY KEY (aml_qtrly_dlr_revw_key);
ALTER TABLE ods.aml_policy_procedure ADD CONSTRAINT aml_policy_procedure_ix_pk PRIMARY KEY (pol_procd_key);
ALTER TABLE ods.aml_foreign_corr_banks ADD CONSTRAINT aml_foreign_corr_banks_ix_pk PRIMARY KEY (forgn_corrsp_bnk_key);
ALTER TABLE ods.aml_fincen ADD CONSTRAINT aml_fincen_ix_pk PRIMARY KEY (aml_fincen_key);
ALTER TABLE ods.aml_fbar_filings ADD CONSTRAINT aml_fbar_filings_ix_pk PRIMARY KEY (fbar_filng_key);
ALTER TABLE ods.aml_dealer_contracts ADD CONSTRAINT aml_dealer_contracts_ix_pk PRIMARY KEY (aml_dlr_contrct_key);
ALTER TABLE ods.aml_cip_letter ADD CONSTRAINT aml_cip_letter_ix_pk PRIMARY KEY (aml_cip_ltr_key);
ALTER TABLE ods.aml_blacklist_country ADD CONSTRAINT aml_blacklist_country_ix_pk PRIMARY KEY (aml_blklist_crty_key);
ALTER TABLE ods.aml_acam_certification ADD CONSTRAINT aml_acam_certification_ix_pk PRIMARY KEY (aml_acam_certfn_key);
ALTER TABLE ods.pmo_tasks ADD CONSTRAINT pmo_tasks_ix_if1 FOREIGN KEY (proj_key) REFERENCES ods.projects(proj_key) ON DELETE SET NULL;
ALTER TABLE ods.invoice ADD CONSTRAINT invoice_ix_if3 FOREIGN KEY (prod_line_key) REFERENCES ods.product_line(prod_line_key) ON DELETE SET NULL;
ALTER TABLE ods.invoice ADD CONSTRAINT invoice_ix_if2 FOREIGN KEY (bud_line_key) REFERENCES ods.budget_line(bud_line_key) ON DELETE SET NULL;
ALTER TABLE ods.invoice ADD CONSTRAINT invoice_ix_if1 FOREIGN KEY (vend_key) REFERENCES ods.vendor(vend_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_workflow_task ADD CONSTRAINT hsg_workflow_task_ix_if2 FOREIGN KEY (hsg_proj_doc_key) REFERENCES ods.hsg_project_document(hsg_proj_doc_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_control_doc_line ADD CONSTRAINT hsg_control_doc_line_ix_if1 FOREIGN KEY (cntl_doc_key) REFERENCES ods.hsg_control_document(cntl_doc_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_control_doc_findings ADD CONSTRAINT hsg_control_doc_finding_ix_if2 FOREIGN KEY (cntl_doc_line_key) REFERENCES ods.hsg_control_doc_line(cntl_doc_line_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_chat_quality_result ADD CONSTRAINT hsg_chat_quality_result_ix_if1 FOREIGN KEY (chat_qual_qstn_key) REFERENCES ods.hsg_chat_quality_question(chat_qual_qstn_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_call_quality_result ADD CONSTRAINT hsg_call_quality_result_ix_if3 FOREIGN KEY (cq_prog_key) REFERENCES ods.hsg_call_quality_program(cq_prog_key) ON DELETE SET NULL;
ALTER TABLE ods.hsg_call_quality_result ADD CONSTRAINT hsg_call_quality_result_ix_if2 FOREIGN KEY (cq_qstn_key) REFERENCES ods.hsg_call_quality_question(cq_qstn_key) ON DELETE SET NULL;
ALTER TABLE ods.decision_list ADD CONSTRAINT decision_list_ix_if2 FOREIGN KEY (proj_key) REFERENCES ods.projects(proj_key) ON DELETE SET NULL;
ALTER TABLE ods.contract_review ADD CONSTRAINT contract_review_ix_if4 FOREIGN KEY (prod_line_key) REFERENCES ods.product_line(prod_line_key) ON DELETE SET NULL;
ALTER TABLE ods.contract_review ADD CONSTRAINT contract_review_ix_if3 FOREIGN KEY (bud_cat_key) REFERENCES ods.budget_category(bud_cat_key) ON DELETE SET NULL;
ALTER TABLE ods.contract_review ADD CONSTRAINT contract_review_ix_if2 FOREIGN KEY (bud_line_key) REFERENCES ods.budget_line(bud_line_key) ON DELETE SET NULL;
ALTER TABLE ods.contract_review ADD CONSTRAINT contract_review_ix_if1 FOREIGN KEY (vend_key) REFERENCES ods.vendor(vend_key) ON DELETE SET NULL;
ALTER TABLE ods.budget_line ADD CONSTRAINT budget_line_ix_if6 FOREIGN KEY (prod_line_key) REFERENCES ods.product_line(prod_line_key) ON DELETE SET NULL;
ALTER TABLE ods.budget_line ADD CONSTRAINT budget_line_ix_if5 FOREIGN KEY (bud_cat_key) REFERENCES ods.budget_category(bud_cat_key) ON DELETE SET NULL;
ALTER TABLE ods.budget_line ADD CONSTRAINT budget_line_ix_if3 FOREIGN KEY (proj_key) REFERENCES ods.projects(proj_key) ON DELETE SET NULL;
ALTER TABLE ods.budget_line ADD CONSTRAINT budget_line_ix_if2 FOREIGN KEY (vend_key) REFERENCES ods.vendor(vend_key) ON DELETE SET NULL;
ALTER TABLE ods.budget_fact ADD CONSTRAINT budget_fact_ix_if1 FOREIGN KEY (bud_line_key) REFERENCES ods.budget_line(bud_line_key) ON DELETE SET NULL;
ALTER TABLE ods.budget ADD CONSTRAINT budget_ix_if1 FOREIGN KEY (proj_key) REFERENCES ods.projects(proj_key) ON DELETE SET NULL;