with open("paper.tex", "r") as f:
    text = f.read()

# Fix Chandra-Toueg and Phi symbols
text = text.replace("(\\diamondsuit P)", "($\\diamondsuit P$)")
text = text.replace("(P)", "($\\diamondsuit P$)")
text = text.replace("and P", "and $\\diamondsuit P$")
text = text.replace(" -accrual", " $\\Phi$-accrual")
text = text.replace("-accrual", "$\\Phi$-accrual")

# Ensure image paths point to results/
text = text.replace("{figure1_unavailability_cdf.pdf}", "{results/figure1_unavailability_cdf.pdf}")
text = text.replace("{figure2_throughput_timeline.pdf}", "{results/figure2_throughput_timeline.pdf}")

with open("paper.tex", "w") as f:
    f.write(text)

print("Updated paper.tex successfully.")
