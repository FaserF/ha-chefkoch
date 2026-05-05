from chefkoch import Recipe
import json

url = "https://www.chefkoch.de/rezepte/1250691230198253/Putengyros-Andrea.html"
recipe = Recipe(url)

# Try to access mangled property
try:
    print(f"Mangled property access: {recipe._Recipe__info_dict.get('@type')}")
except AttributeError:
    print("Cannot access _Recipe__info_dict")

# Let's try to monkeypatch it with a simple property
def patched_info_dict(self):
    if not hasattr(self, "_Recipe__soup"):
        return {}
    scripts = self._Recipe__soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.text)
            if isinstance(data, dict) and data.get("@type") == "Recipe":
                return data
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        return item
        except:
            continue
    return {}

# Apply patch
Recipe._Recipe__info_dict = property(patched_info_dict)

# Try again
recipe2 = Recipe(url)
print(f"Patched Title: {recipe2.title}")
print(f"Patched Rating: {recipe2.rating}")
print(f"Patched Ratings Count: {recipe2.number_ratings}")
print(f"Patched Reviews: {recipe2.number_reviews}")
print(f"Patched Ingredients: {len(recipe2.ingredients)}")
